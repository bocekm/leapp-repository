from collections import namedtuple

import pytest

from leapp.exceptions import StopActorExecutionError
from leapp.libraries.actor import userspacegen
from leapp.libraries.common import rhsm
from leapp.libraries.stdlib import api
from leapp.models import (CustomTargetRepository, RHELTargetRepository,
                          TargetRepositories, Version)


class CurrentActorMocked(object):
    configuration = namedtuple('configuration', ['version'])(Version(source='7.6', target='8.0'))


def test_gather_target_repositories(monkeypatch):
    monkeypatch.setattr(api, 'current_actor', CurrentActorMocked)
    # The available RHSM repos
    monkeypatch.setattr(rhsm, 'get_available_repo_ids', lambda x, releasever: ['repoidX', 'repoidY', 'repoidZ'])
    monkeypatch.setattr(rhsm, 'skip_rhsm', lambda: False)
    # The required RHEL repos based on the repo mapping and PES data + custom repos required by third party actors
    monkeypatch.setattr(api, 'consume', lambda x: iter([TargetRepositories(
        rhel_repos=[RHELTargetRepository(repoid='repoidX'),
                    RHELTargetRepository(repoid='repoidY')],
        custom_repos=[CustomTargetRepository(repoid='repoidCustom')])]))

    target_repoids = userspacegen.gather_target_repositories(None)

    assert target_repoids == ['repoidX', 'repoidY', 'repoidCustom']


def test_gather_target_repositories_none_available(monkeypatch):
    monkeypatch.setattr(api, 'current_actor', CurrentActorMocked)
    monkeypatch.setattr(rhsm, 'get_available_repo_ids', lambda x, releasever: [])
    monkeypatch.setattr(rhsm, 'skip_rhsm', lambda: False)
    with pytest.raises(StopActorExecutionError) as err:
        userspacegen.gather_target_repositories(None)
    assert "Cannot find required basic RHEL 8 repositories" in str(err)


@pytest.mark.skip(reason="Currently not implemented in the actor. It's TODO.")
def test_gather_target_repositories_required_not_available(monkeypatch):
    # If the repos Leapp has identified as required for the upgrade, based on the repo mapping and PES data,
    # an exception shall be raised

    monkeypatch.setattr(api, 'current_actor', CurrentActorMocked)
    # The available RHSM repos
    monkeypatch.setattr(rhsm, 'get_available_repo_ids', lambda x, releasever: ['repoidA', 'repoidB', 'repoidC'])
    monkeypatch.setattr(rhsm, 'skip_rhsm', lambda: False)
    # The required RHEL repos based on the repo mapping and PES data + custom repos required by third party actors
    monkeypatch.setattr(api, 'consume', lambda x: iter([TargetRepositories(
        rhel_repos=[RHELTargetRepository(repoid='repoidX'),
                    RHELTargetRepository(repoid='repoidY')],
        custom_repos=[CustomTargetRepository(repoid='repoidCustom')])]))

    with pytest.raises(StopActorExecutionError) as err:
        userspacegen.gather_target_repositories(None)
    assert "Cannot find required basic RHEL 8 repositories" in str(err)
