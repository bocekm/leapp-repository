from leapp import reporting
from leapp.actors import Actor
from leapp.libraries.stdlib import api
from leapp.models import Report
from leapp.reporting import create_report
from leapp.tags import IPUWorkflowTag, TargetTransactionChecksPhaseTag


class ReportSetTargetRelease(Actor):
    """
    Reports that a release will be set in the subscription-manager after the upgrade.
    """

    name = 'report_set_target_release'
    consumes = ()
    produces = (Report,)
    tags = (IPUWorkflowTag, TargetTransactionChecksPhaseTag)

    def process(self):
        target_version = api.current_actor().configuration.version.target
        create_report([
            reporting.Title(
                'The subscription-manager release is going to be set to {release}'.format(release=target_version)),
            reporting.Summary(
                'After the upgrade has completed the release of the subscription-manager will be set to {release}.'
                ' This will ensure that you will receive and keep the version you choose to upgrade to.'.
                format(release=target_version)
            ),
            reporting.Severity(reporting.Severity.LOW),
            reporting.Tags([reporting.Tags.UPGRADE_PROCESS]),
            reporting.RelatedResource('package', 'subscription-manager')
        ])
