from leapp import reporting
from leapp.libraries.stdlib import api


def process():
    # TODO: skip if users are not using rhsm at all (RHELLEAPP-201)
    target_version = api.current_actor().configuration.version.target
    # The non-static title is against our best-practicess, but in this case
    # it make sense to print the specific info. Anyway, feel free to change
    # it to static string.
    reporting.create_report([
        reporting.Title(
            'The subscription-manager release is going to be set to {release}'.format(release=target_version)),
        reporting.Summary(
            'After the upgrade has completed the release of the subscription-manager will be set to {release}.'
            ' This will ensure that you will receive and keep the version you choose to upgrade to.'
            .format(release=target_version)
        ),
        reporting.Severity(reporting.Severity.LOW),
        reporting.Tags([reporting.Tags.UPGRADE_PROCESS]),
        reporting.RelatedResource('package', 'subscription-manager')
    ])
