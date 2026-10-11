"""Roam Version Control groups — the relationship between a block's versions, derived from a node network.

A block authored with Roam's Version Control feature is several block entities, all at one
``order`` under one parent, grouped by a *version group* entity whose only attribute is a
``:vc/blocks`` ref to each version.  The parent's ``children`` names just the *selected*
version; the others are reachable only through the group.  In a
:data:`~guffin.roam.node_network.NodeNetwork` the group arrives as a
:attr:`~guffin.roam.node.NodeType.VERSION_GROUP` node whose ``blocks`` stubs name the versions,
and the selection is implicit: it is whichever member some node's ``children`` lists.

This module reads that relationship off the raw nodes into one explicit value per group, and
checks the invariants the raw rows must satisfy for the reading to be well-defined.

Public symbols:

- :class:`VersionGroup` — one block's version group: its members, the one that is selected, and
  the parent whose ``children`` selects it.
- :func:`all_version_members_present` — :data:`~guffin.common.validation.Validator` requiring every
  member id a group names to resolve to a node in the network.
- :func:`all_version_members_share_placement` — :data:`~guffin.common.validation.Validator` requiring a
  group's members to be blocks sharing one ``order`` and one set of ``parents``.
- :func:`exactly_one_version_selected` — :data:`~guffin.common.validation.Validator` requiring exactly
  one member of each group to appear in some node's ``children``.
- :func:`validate_version_groups` — run every version-group validator over a network, accumulating a
  :class:`~guffin.common.validation.ValidationResult`.
- :func:`version_groups_of` — derive every :class:`VersionGroup` in a network, keyed by group id,
  optionally scoped to groups touching a given set of node ids.
- :func:`version_group_by_member_id` — pivot a group map to one keyed by member id.
"""

from collections.abc import Mapping, Set
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, SkipValidation, model_validator, validate_call

from guffin.common.validation import ValidationError, ValidationResult, validate_all
from guffin.roam.node import NodeType, RoamNode, node_type
from guffin.roam.node_network import NodeNetwork, parent_by_child_id
from guffin.roam.primitives import Id, Uid

# Already-validated, frozen RoamNodes on a traversal path; see node_network for why SkipValidation.
_TrustedNetwork = Annotated[NodeNetwork, SkipValidation]


class VersionGroup(BaseModel):
    """One block's version group: the versions, the selected one, and the parent selecting it.

    Attributes:
        uid: The group entity's stable identifier.
        id: The group entity's Datomic entity id.
        parent_id: The id of the node whose ``children`` names the selected version — the parent
            every member shares.
        member_ids: The ids of the version blocks, in the order the group entity lists them.
            Never empty, never repeating.
        selected_id: The member the parent's ``children`` names; always one of *member_ids*.
    """

    model_config = ConfigDict(frozen=True)

    uid: Uid = Field(description="The group entity's :block/uid.")
    id: Id = Field(description="The group entity's :db/id.")
    parent_id: Id = Field(description="The id of the node whose children names the selected version.")
    member_ids: tuple[Id, ...] = Field(description="The version blocks' ids, in the group entity's order.")
    selected_id: Id = Field(description="The member the parent's children names; one of member_ids.")

    @model_validator(mode="after")
    def _validate_membership(self) -> VersionGroup:
        """Require a non-empty, repeat-free membership that contains the selected id."""
        if not self.member_ids:
            raise ValueError(f"version group uid={self.uid!r} has no members")
        if len(set(self.member_ids)) != len(self.member_ids):
            raise ValueError(f"version group uid={self.uid!r} lists a member more than once: {self.member_ids}")
        if self.selected_id not in self.member_ids:
            raise ValueError(
                f"version group uid={self.uid!r}: selected id {self.selected_id} is not a member of {self.member_ids}"
            )
        return self

    @property
    def unselected_ids(self) -> tuple[Id, ...]:
        """The members the parent's ``children`` does not name, in membership order."""
        return tuple(member_id for member_id in self.member_ids if member_id != self.selected_id)


def _group_nodes(network: NodeNetwork) -> list[RoamNode]:
    """The version-group nodes of *network*, in network order."""
    return [node for node in network if node_type(node) is NodeType.VERSION_GROUP]


def _member_ids(group: RoamNode) -> tuple[Id, ...]:
    """The member ids a version-group node names, in its ``blocks`` order."""
    return tuple(stub.id for stub in group.blocks or [])


@validate_call
def all_version_members_present(network: _TrustedNetwork) -> ValidationError | None:
    """Return ``None`` when every member id a version group names resolves to a node in *network*.

    Args:
        network: The collection of nodes to examine.

    Returns:
        ``None`` if every member id resolves; a :class:`~guffin.common.validation.ValidationError`
        listing the sorted absent member ids and the sorted ids of the groups naming them otherwise.
    """
    network_ids: Final[set[Id]] = {node.id for node in network}
    violations: Final[list[tuple[Id, Id]]] = [
        (group.id, member_id)
        for group in _group_nodes(network)
        for member_id in _member_ids(group)
        if member_id not in network_ids
    ]
    if not violations:
        return None
    missing_ids: Final[list[Id]] = sorted({member_id for _, member_id in violations})
    group_ids: Final[list[Id]] = sorted({group_id for group_id, _ in violations})
    return ValidationError(
        message=f"version member ids absent from network: {missing_ids}; named by groups: {group_ids}",
        validator=all_version_members_present,
    )


@validate_call
def all_version_members_share_placement(network: _TrustedNetwork) -> ValidationError | None:
    """Return ``None`` when each group's members are blocks sharing one ``order`` and one ``parents`` set.

    The versions of one block occupy one position: Roam gives every version the same ``order``
    under the same ancestors, and only a block can be a version.  A group with a member absent
    from *network* is skipped here; :func:`all_version_members_present` reports it.

    Args:
        network: The collection of nodes to examine.

    Returns:
        ``None`` if every group's members agree; a :class:`~guffin.common.validation.ValidationError`
        naming each disagreeing group and what its members disagree on otherwise.
    """
    by_id: Final[dict[Id, RoamNode]] = {node.id: node for node in network}
    findings: Final[list[str]] = []
    for group in _group_nodes(network):
        members: list[RoamNode] = [by_id[member_id] for member_id in _member_ids(group) if member_id in by_id]
        if len(members) != len(_member_ids(group)):
            continue
        non_blocks: list[Id] = [member.id for member in members if member.string is None]
        if non_blocks:
            findings.append(f"group {group.id}: members that are not blocks: {sorted(non_blocks)}")
            continue
        orders: set[int | None] = {member.order for member in members}
        parent_sets: set[frozenset[Id]] = {frozenset(stub.id for stub in member.parents or []) for member in members}
        if len(orders) > 1:
            findings.append(f"group {group.id}: members disagree on order: {sorted(orders, key=str)}")
        if len(parent_sets) > 1:
            findings.append(f"group {group.id}: members disagree on parents: {sorted(sorted(s) for s in parent_sets)}")
    if not findings:
        return None
    return ValidationError(message="; ".join(findings), validator=all_version_members_share_placement)


@validate_call
def exactly_one_version_selected(network: _TrustedNetwork) -> ValidationError | None:
    """Return ``None`` when exactly one member of each version group appears in some node's ``children``.

    The selected version is the one member the parent's ``children`` names; a group with none
    selected has no displayed version, and one with several has no single one.  A group with a
    member absent from *network* is skipped here; :func:`all_version_members_present` reports it.

    Args:
        network: The collection of nodes to examine.

    Returns:
        ``None`` if every group has exactly one selected member; a
        :class:`~guffin.common.validation.ValidationError` naming each group with its selected
        count otherwise.
    """
    network_ids: Final[set[Id]] = {node.id for node in network}
    parent_by_child: Final[dict[Id, Id]] = parent_by_child_id(network)
    findings: Final[list[str]] = []
    for group in _group_nodes(network):
        member_ids: tuple[Id, ...] = _member_ids(group)
        if any(member_id not in network_ids for member_id in member_ids):
            continue
        selected: list[Id] = [member_id for member_id in member_ids if member_id in parent_by_child]
        if len(selected) != 1:
            findings.append(f"group {group.id}: {len(selected)} of {len(member_ids)} members selected: {selected}")
    if not findings:
        return None
    return ValidationError(message="; ".join(findings), validator=exactly_one_version_selected)


@validate_call
def validate_version_groups(network: _TrustedNetwork) -> ValidationResult:
    """Run every version-group validator over *network* and return the accumulated result.

    Runs :func:`all_version_members_present`, :func:`all_version_members_share_placement`, and
    :func:`exactly_one_version_selected` via :func:`~guffin.common.validation.validate_all`; all
    run regardless of prior failures.  A network with no version groups is vacuously valid.

    Args:
        network: The collection of nodes to validate.

    Returns:
        A :class:`~guffin.common.validation.ValidationResult` that is valid when every group in
        *network* is well-formed, or carries one error per failed validator otherwise.
    """
    return validate_all(
        network,
        [
            all_version_members_present,
            all_version_members_share_placement,
            exactly_one_version_selected,
        ],
    )


@validate_call
def version_groups_of(network: _TrustedNetwork, scope_ids: Set[Id] | None = None) -> dict[Id, VersionGroup]:
    """Derive every :class:`VersionGroup` in *network*, keyed by group id.

    Reads each version-group node's membership off its ``blocks`` and its selection off the one
    member some node's ``children`` names; that node is the group's parent.  With *scope_ids*,
    only groups with at least one member in the scope are returned, so a tree can keep the
    groups of its own and its referenced nodes while a wider network holds more.

    Args:
        network: The collection of nodes to read the groups from.
        scope_ids: When given, the node ids a group must touch (through a member) to be included.

    Returns:
        A ``dict[Id, VersionGroup]`` mapping each included group's id to its derived relationship;
        empty when *network* holds no version groups.

    Raises:
        ValueError: If *network* fails :func:`validate_version_groups`; the message lists every
            failure found.
    """
    result: Final[ValidationResult] = validate_version_groups(network)
    if not result.is_valid:
        raise ValueError("version group validation failed: " + "; ".join(str(error) for error in result.errors))
    parent_by_child: Final[dict[Id, Id]] = parent_by_child_id(network)
    groups: Final[dict[Id, VersionGroup]] = {}
    for group in _group_nodes(network):
        member_ids: tuple[Id, ...] = _member_ids(group)
        if scope_ids is not None and not any(member_id in scope_ids for member_id in member_ids):
            continue
        selected_id: Id = next(member_id for member_id in member_ids if member_id in parent_by_child)
        groups[group.id] = VersionGroup(
            uid=group.uid,
            id=group.id,
            parent_id=parent_by_child[selected_id],
            member_ids=member_ids,
            selected_id=selected_id,
        )
    return groups


@validate_call
def version_group_by_member_id(groups: Mapping[Id, VersionGroup]) -> dict[Id, VersionGroup]:
    """Pivot *groups* to a map from each member id to the group it is a version in.

    Args:
        groups: Version groups keyed by group id, as :func:`version_groups_of` returns them.

    Returns:
        A ``dict[Id, VersionGroup]`` with one entry per member of every group.
    """
    return {member_id: group for group in groups.values() for member_id in group.member_ids}
