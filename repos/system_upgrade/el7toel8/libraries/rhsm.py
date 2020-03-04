import contextlib
import functools
import os
import re
import time

from leapp.exceptions import StopActorExecutionError
from leapp.libraries.common.config import get_product_type
from leapp.libraries.stdlib import CalledProcessError, api

_RE_REPO_UID = re.compile(r'Repo ID:\s*([^\s]+)')
_RE_RELEASE = re.compile(r'Release:\s*([^\s]+)')
_RE_SKU_CONSUMED = re.compile(r'SKU:\s*([^\s]+)')
_ATTEMPTS = 5
_RETRY_SLEEP = 5


class Repo(object):
    def __init__(self):
        self.id = None
        self.file = None


def _rhsm_retry(max_attempts, sleep=None):
    """
    A decorator to retry executing a function/method if unsuccessful.

    The function/method execution is considered unsuccessful when it raises StopActorExecutionError.

    :param max_attempts: Maximum number of attempts to execute the decorated function/method.
    :param sleep: Time to wait between attempts. In seconds.
    """
    def impl(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            attempts = 0
            while True:
                attempts += 1
                try:
                    return f(*args, **kwargs)
                except StopActorExecutionError:
                    if max_attempts <= attempts:
                        api.current_logger().warning(
                            'Attempt %d of %d to perform %s failed. Maximum number of retries has been reached.',
                            attempts, max_attempts, f.__name__)
                        raise
                    if sleep:
                        api.current_logger().info(
                            'Attempt %d of %d to perform %s failed - Retrying after %s seconds',
                            attempts, max_attempts, f.__name__, str(sleep))
                        time.sleep(sleep)
                    else:
                        api.current_logger().info(
                            'Attempt %d of %d to perform %s failed - Retrying...', attempts, max_attempts, f.__name__)
        return wrapper
    return impl


@contextlib.contextmanager
def _handle_rhsm_exceptions(hint=None):
    """
    Context manager based function that handles exceptions of `run` for the subscription manager calls.
    """
    try:
        yield
    except OSError as e:
        api.current_logger().error('Failed to execute subscription-manager executable')
        raise StopActorExecutionError(
            message='Unable to execute subscription-manager executable: {}'.format(str(e)),
            details={
                'hint': 'Please ensure subscription-manager is installed and executable.'
            }
        )
    except CalledProcessError as e:
        raise StopActorExecutionError(
            message='A subscription-manager command failed to execute',
            details={
                'details': str(e),
                'stderr': e.stderr,
                'hint': hint or 'Please ensure you have a valid RHEL subscription and your network is up.'
            }
        )


def skip_rhsm():
    """ Check whether we should skip RHSM related code """
    return os.getenv('LEAPP_DEVEL_SKIP_RHSM', '0') == '1'


def with_rhsm(f):
    """ Decorator to allow skipping RHSM functions by executing a no-op """
    if skip_rhsm():
        @functools.wraps(f)
        def _no_op(*args, **kwargs):
            return
        return _no_op
    return f


@with_rhsm
def get_attached_skus(context, rhsm_info):
    """
    Retrieve the list of SKU the system is attached to with the subscription manager.

    :param context: An instance of a mounting.IsolatedActions class
    :type context: mounting.IsolatedActions class
    :param rhsm_info: An instance of a RHSMInfo derived model.
    :type rhsm_info: RHSMInfo derived model
    """
    if not rhsm_info.attached_skus:
        with _handle_rhsm_exceptions():
            result = context.call(['subscription-manager', 'list', '--consumed'], split=False)
            rhsm_info.attached_skus = _RE_SKU_CONSUMED.findall(result['stdout'])


def get_available_repo_uids(context, rhsm_info):
    """Deprecated. Repositories have ids, not uids. Use get_available_repo_ids instead."""
    return get_available_repo_ids(context, rhsm_info)


def get_available_repo_ids(context, rhsm_info):
    """
    Retrieve repo ids of all the repositories available through the subscription-manager.

    :param context: An instance of a mounting.IsolatedActions class
    :type context: mounting.IsolatedActions class
    :param rhsm_info: An instance of a RHSMInfo derived model.
    :type rhsm_info: RHSMInfo derived model
    """
    if not rhsm_info.available_repos:
        result = context.call(['yum', 'repoinfo'])
        all_repos = list(get_repos(result['stdout']))
        rhsm_info.available_repos = [repo.id for repo in all_repos if repo.file == '/etc/yum.repos.d/redhat.repo']


def get_repos(repos_raw):
    """
    Generator providing all the repos available through yum/dnf.

    :rtype: Iterator[:py:class:`leapp.libraries.common.rhsm.Repo`]
    """
    # TODO: Log a warning on the following msg that `yum repoinfo` may produce:
    #  "Repository rhel-7-server-eus-rpms is listed more than once in the configuration"

    # Split all the available repos per one repo
    for repo_raw_params in re.findall(
            r"Repo-id.*?Repo-filename.*?\n",
            repos_raw,
            re.DOTALL | re.MULTILINE):
        yield parse_repo_params(repo_raw_params)


def parse_repo_params(repo_raw_params):
    """Parse multiline string holding repo parameters to distill the important ones."""
    repo = Repo()
    try:
        repo.id = get_repo_param(r"^Repo-id\s+:\s+(.*?)(/.*)?$", repo_raw_params, "Repo-id")
        repo.file = get_repo_param(r"^Repo-filename:\s+(.*?)$", repo_raw_params, "Repo-filename")
    except ValueError, err:
        api.current_logger().warn("Failed to parse the '%s' repo parameter of the `yum repoinfo` output", err.args[0])

    return repo


def get_repo_param(pattern, repo_raw_params, param):
    """Parse a string with all the repo params to get the value of a single repo param."""
    sub_attr = re.search(pattern,
                         repo_raw_params,
                         re.MULTILINE | re.DOTALL)
    if sub_attr:
        return sub_attr.group(1)
    else:
        raise ValueError(param)


def get_enabled_repo_uids(context, rhsm_info):
    """Deprecated. Repositories have ids, not uids. Use get_enabled_repo_ids instead."""
    return get_enabled_repo_ids(context, rhsm_info)


@with_rhsm
def get_enabled_repo_ids(context, rhsm_info):
    """
    Retrieve names of all the repositories enabled through the subscription-manager.

    :param context: An instance of a mounting.IsolatedActions class
    :type context: mounting.IsolatedActions class
    :param rhsm_info: An instance of a RHSMInfo derived model.
    :type rhsm_info: RHSMInfo derived model
    """
    if not rhsm_info.enabled_repos:
        with _handle_rhsm_exceptions():
            result = context.call(['subscription-manager', 'repos', '--list-enabled'], split=False)
            rhsm_info.enabled_repos = _RE_REPO_UID.findall(result['stdout'])


@with_rhsm
@_rhsm_retry(max_attempts=_ATTEMPTS, sleep=_RETRY_SLEEP)
def unset_release(context):
    """
    Unset the configured release from the subscription manager.

    :param context: An instance of a mounting.IsolatedActions class
    :type context: mounting.IsolatedActions class
    """
    with _handle_rhsm_exceptions():
        context.call(['subscription-manager', 'release', '--unset'], split=False)


@with_rhsm
@_rhsm_retry(max_attempts=_ATTEMPTS, sleep=_RETRY_SLEEP)
def set_release(context, release):
    """
    Set the release (RHEL minor version) through the subscription-manager.

    :param context: An instance of a mounting.IsolatedActions class
    :type context: mounting.IsolatedActions class
    :param release: Release to set the subscription manager to.
    :type release: str
    """
    with _handle_rhsm_exceptions():
        context.call(['subscription-manager', 'release', '--set', release], split=False)


@with_rhsm
def get_release(context, rhsm_info):
    """
    Retrieves the release the subscription manager has been pinned to, if applicable.

    :param context: An instance of a mounting.IsolatedActions class
    :type context: mounting.IsolatedActions class
    :param rhsm_info: An instance of a RHSMInfo derived model.
    :type rhsm_info: RHSMInfo derived model
    """
    if rhsm_info.release is None:
        with _handle_rhsm_exceptions():
            result = context.call(['subscription-manager', 'release'], split=False)
            result = _RE_RELEASE.findall(result['stdout'])
            rhsm_info.release = result[0] if result else ''


@with_rhsm
@_rhsm_retry(max_attempts=_ATTEMPTS, sleep=_RETRY_SLEEP)
def refresh(context):
    """
    Calls 'subscription-manager refresh'

    :param context: An instance of a mounting.IsolatedActions class
    :type context: mounting.IsolatedActions class
    """
    with _handle_rhsm_exceptions():
        context.call(['subscription-manager', 'refresh'], split=False)


@with_rhsm
def get_existing_product_certificates(context, rhsm_info):
    """
    Retrieves information about existing product certificates on the system.

    :param context: An instance of a mounting.IsolatedActions class
    :type context: mounting.IsolatedActions class
    :param rhsm_info: An instance of a RHSMInfo derived model.
    :type rhsm_info: RHSMInfo derived model
    """
    if not rhsm_info.existing_product_certificates:
        for path in ('/etc/pki/product', '/etc/pki/product-default'):
            if not os.path.isdir(context.full_path(path)):
                continue
            certs = [os.path.join(path, f) for f in os.listdir(context.full_path(path))
                     if os.path.isfile(os.path.join(context.full_path(path), f))]
            if not certs:
                continue
            rhsm_info.existing_product_certificates.extend(certs)


@contextlib.contextmanager
def switch_certificate(context, rhsm_info, cert_path):
    """
    Perform all actions needed to switch the passed RHSM product certificate.

    This function will copy the certificate to /etc/pki/product, and /etc/pki/product-default if necessary, and
    remove other product certificates from there.

    :param context: An instance of a mounting.IsolatedActions class
    :type context: mounting.IsolatedActions class
    :param rhsm_info: An instance of a RHSMInfo derived model.
    :type rhsm_info: RHSMInfo derived model
    :param cert_path: Path to the product certificate to switch to.
    :type cert_path: string
    """
    # Back up product certificates
    pki_path = '/etc/pki'
    pki_backup_path = '/etc/pki.bak'
    context.call(['rm', '-rf', pki_backup_path], checked=False)
    context.call(['cp', '-a', pki_path, pki_backup_path], checked=False)

    for existing in rhsm_info.existing_product_certificates:
        try:
            context.remove(existing)
        except OSError:
            api.current_logger().warn('Failed to remove existing certificate: %s', existing, exc_info=True)

    for path in ('/etc/pki/product', '/etc/pki/product-default'):
        if os.path.isdir(context.full_path(path)):
            context.copy_to(cert_path, os.path.join(path, os.path.basename(cert_path)))

    # Restore product certificates from the backup
    context.call(['rm', '-rf', pki_path], checked=False)
    context.call(['cp', '-a', pki_backup_path, pki_path], checked=False)


@with_rhsm
def scan_rhsm_info(context, rhsm_info):
    """
    Gather all RHSM information

    :param context: An instance of a mounting.IsolatedActions class
    :type context: mounting.IsolatedActions class
    :param rhsm_info: An instance of a RHSMInfo derived model.
    :type rhsm_info: RHSMInfo derived model
    """
    get_attached_skus(context, rhsm_info)
    get_available_repo_ids(context, rhsm_info)
    get_enabled_repo_ids(context, rhsm_info)
    get_release(context, rhsm_info)
    get_existing_product_certificates(context, rhsm_info)
