from leapp.actors import Actor
from leapp.models import RpmTransactionTasks, FilteredRpmTransactionTasks, InstalledRedHatSignedRPM
from leapp.tags import IPUWorkflowTag, FactsPhaseTag


class FilterRpmTransactionTasks(Actor):
    name = 'check_rpm_transaction_events'
    description = 'Filters RPM transaction events to only include relevant events based on installed RPM'
    consumes = (RpmTransactionTasks, InstalledRedHatSignedRPM,)
    produces = (FilteredRpmTransactionTasks,)
    tags = (IPUWorkflowTag, FactsPhaseTag)

    def process(self):
        installed_pkgs = set()
        for rpm_pkgs in self.consume(InstalledRedHatSignedRPM):
            installed_pkgs.update([pkg.name for pkg in rpm_pkgs.items])

        to_install = set()
        to_remove = set()
        to_keep = set()
        for event in self.consume(RpmTransactionTasks):
            to_install.update(event.to_install)
            to_remove.update(installed_pkgs.intersection(event.to_remove))
            to_keep.update(installed_pkgs.intersection(event.to_keep))

        to_remove.difference_update(to_keep)

        self.produce(FilteredRpmTransactionTasks(
            to_install=list(to_install),
            to_remove=list(to_remove),
            to_keep=list(to_keep)))
