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
    monkeypatch.setattr(rhsm, 'get_available_repo_ids', lambda x, releasever: ['repoidX', 'repoidY', 'repoidZ'])
    monkeypatch.setattr(rhsm, 'skip_rhsm', lambda: False)
    monkeypatch.setattr(api, 'consume', lambda x: iter([TargetRepositories(
        rhel_repos=[RHELTargetRepository(repoid='repoidX'),
                    RHELTargetRepository(repoid='repoidY')],
        custom_repos=[CustomTargetRepository(repoid='repoidCustom')])]))

    target_repoids = userspacegen.gather_target_repositories(None)

    assert all([a == b for a, b in zip(target_repoids, ['repoidX', 'repoidY'])])


def test_gather_target_repositories_no_available(monkeypatch):
    monkeypatch.setattr(api, 'current_actor', CurrentActorMocked)
    monkeypatch.setattr(rhsm, 'get_available_repo_ids', lambda x, releasever: [])
    monkeypatch.setattr(rhsm, 'skip_rhsm', lambda: False)
    with pytest.raises(StopActorExecutionError) as err:
        userspacegen.gather_target_repositories(None)
    assert "Cannot find" in str(err)
