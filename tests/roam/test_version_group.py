"""Tests for the version_group module."""

from typing import Final

import pytest
import yaml
from conftest import FIXTURES_YAML_DIR, YamlFixtureLoader
from pydantic import ValidationError

from guffin.common.validation import ValidationResult
from guffin.roam.node import NodeType, RoamNode
from guffin.roam.node_network import NodeNetwork
from guffin.roam.node_tree import NodeTree
from guffin.roam.primitives import IdObject
from guffin.roam.version_group import (
    VersionGroup,
    all_version_members_present,
    all_version_members_share_node_type,
    all_version_members_share_placement,
    exactly_one_version_selected,
    no_version_member_has_children,
    validate_version_groups,
    version_groups_by_member_id,
    version_groups_of,
)

# [[Test Article]] 0, block 3.4: a child authored with three versions, the second selected.
_GROUP_UID: Final[str] = "e9j_vHjGQ"
_PARENT_UID: Final[str] = "xPUIusgqA"
_VERSION_UIDS: Final[tuple[str, str, str]] = ("PUrwWBbbi", "zHbMF7Ozq", "YYysqBFqy")
_SELECTED_UID: Final[str] = "zHbMF7Ozq"


def _article0_network() -> NodeNetwork:
    """Every node of the recorded ``[[Test Article]] 0`` with-refs fetch, the group row included."""
    by_uid: dict[str, dict[str, object]] = yaml.load(
        (FIXTURES_YAML_DIR / "test_article_0_nodes_by_uid.yaml").read_text(), Loader=YamlFixtureLoader
    )
    return [RoamNode.model_validate(raw) for raw in by_uid.values()]


_PAGE_ID: Final[int] = 1
_PARENT_ID: Final[int] = 2
_V1_ID: Final[int] = 11
_V2_ID: Final[int] = 12
_V3_ID: Final[int] = 13
_GROUP_ID: Final[int] = 20


def _page(children: list[int]) -> RoamNode:
    return RoamNode(uid="page00000", id=_PAGE_ID, title="Page", children=[IdObject(id=c) for c in children])


def _block(uid: str, node_id: int, order: int, parents: list[int], children: list[int] | None = None) -> RoamNode:
    return RoamNode(
        uid=uid,
        id=node_id,
        string=f"block {uid}",
        order=order,
        page=IdObject(id=_PAGE_ID),
        parents=[IdObject(id=p) for p in parents],
        children=[IdObject(id=c) for c in children] if children is not None else None,
    )


def _group(member_ids: list[int], node_id: int = _GROUP_ID, uid: str = "group0000") -> RoamNode:
    return RoamNode(uid=uid, id=node_id, blocks=[IdObject(id=m) for m in member_ids])


def _versioned_network(
    *,
    selected: list[int] | None = None,
    orders: tuple[int, int, int] = (0, 0, 0),
    member_ids: list[int] | None = None,
) -> NodeNetwork:
    """A page → parent → three-version arrangement, selection and placement adjustable."""
    chosen: Final[list[int]] = [_V3_ID] if selected is None else selected
    return [
        _page([_PARENT_ID]),
        _block("parent000", _PARENT_ID, 0, [_PAGE_ID], children=chosen),
        _block("version01", _V1_ID, orders[0], [_PAGE_ID, _PARENT_ID]),
        _block("version02", _V2_ID, orders[1], [_PAGE_ID, _PARENT_ID]),
        _block("version03", _V3_ID, orders[2], [_PAGE_ID, _PARENT_ID]),
        _group([_V1_ID, _V2_ID, _V3_ID] if member_ids is None else member_ids),
    ]


class TestVersionGroupModel:
    """Tests for the VersionGroup model's own invariants."""

    def test_valid_group(self) -> None:
        """A group with a selected member among its members is accepted, and exposes the rest."""
        group = VersionGroup(
            uid="group0000", id=20, parent_id=2, member_ids=(11, 12, 13), selected_id=12, node_type=NodeType.TEXT_BLOCK
        )
        assert group.unselected_ids == (11, 13)

    def test_selected_must_be_a_member(self) -> None:
        """The selected id must be one of the member ids."""
        with pytest.raises(ValidationError, match="is not a member"):
            VersionGroup(
                uid="group0000", id=20, parent_id=2, member_ids=(11, 12), selected_id=13, node_type=NodeType.TEXT_BLOCK
            )

    def test_members_never_empty(self) -> None:
        """A group with no members is rejected."""
        with pytest.raises(ValidationError, match="has no members"):
            VersionGroup(
                uid="group0000", id=20, parent_id=2, member_ids=(), selected_id=11, node_type=NodeType.TEXT_BLOCK
            )

    def test_members_never_repeat(self) -> None:
        """A member listed twice is rejected."""
        with pytest.raises(ValidationError, match="more than once"):
            VersionGroup(
                uid="group0000", id=20, parent_id=2, member_ids=(11, 11), selected_id=11, node_type=NodeType.TEXT_BLOCK
            )

    def test_frozen(self) -> None:
        """The model is immutable."""
        group = VersionGroup(
            uid="group0000", id=20, parent_id=2, member_ids=(11, 12), selected_id=11, node_type=NodeType.TEXT_BLOCK
        )
        with pytest.raises(ValidationError):
            group.selected_id = 12  # type: ignore[misc]


class TestValidators:
    """Tests for the three version-group validators over hand-built networks."""

    def test_well_formed_network_passes_every_validator(self) -> None:
        """The reference arrangement passes all three."""
        network: Final[NodeNetwork] = _versioned_network()
        assert all_version_members_present(network) is None
        assert all_version_members_share_placement(network) is None
        assert all_version_members_share_node_type(network) is None
        assert exactly_one_version_selected(network) is None
        assert no_version_member_has_children(network) is None
        assert validate_version_groups(network).is_valid

    def test_network_without_groups_is_vacuously_valid(self) -> None:
        """A network with no version group passes."""
        network: Final[NodeNetwork] = [_page([_PARENT_ID]), _block("parent000", _PARENT_ID, 0, [_PAGE_ID])]
        assert validate_version_groups(network).is_valid

    def test_missing_member_is_reported(self) -> None:
        """A member id the network does not hold fails all_version_members_present, naming it."""
        network: Final[NodeNetwork] = _versioned_network(member_ids=[_V1_ID, _V2_ID, _V3_ID, 99])
        error = all_version_members_present(network)
        assert error is not None
        assert "[99]" in error.message
        assert f"[{_GROUP_ID}]" in error.message

    def test_missing_member_skips_the_other_validators(self) -> None:
        """Placement and selection are not judged for a group with an absent member."""
        network: Final[NodeNetwork] = _versioned_network(member_ids=[_V1_ID, _V2_ID, _V3_ID, 99])
        assert all_version_members_share_placement(network) is None
        assert all_version_members_share_node_type(network) is None
        assert exactly_one_version_selected(network) is None
        assert no_version_member_has_children(network) is None
        result: Final[ValidationResult] = validate_version_groups(network)
        assert [error.validator for error in result.errors] == [all_version_members_present]

    def test_disagreeing_order_is_reported(self) -> None:
        """Members at different orders fail all_version_members_share_placement."""
        error = all_version_members_share_placement(_versioned_network(orders=(0, 1, 0)))
        assert error is not None
        assert "disagree on order" in error.message

    def test_disagreeing_parents_is_reported(self) -> None:
        """Members under different parents fail all_version_members_share_placement."""
        network: Final[NodeNetwork] = _versioned_network()
        stray: Final[RoamNode] = _block("version02", _V2_ID, 0, [_PAGE_ID])
        network_with_stray: Final[NodeNetwork] = [stray if n.id == _V2_ID else n for n in network]
        error = all_version_members_share_placement(network_with_stray)
        assert error is not None
        assert "disagree on parents" in error.message

    def test_non_block_member_is_reported(self) -> None:
        """A page named as a member fails all_version_members_share_placement."""
        network: Final[NodeNetwork] = _versioned_network(member_ids=[_V1_ID, _V2_ID, _V3_ID, _PAGE_ID])
        error = all_version_members_share_placement(network)
        assert error is not None
        assert "not blocks" in error.message

    def test_mixed_node_types_are_reported(self) -> None:
        """A group whose members classify differently fails all_version_members_share_node_type."""
        network: Final[NodeNetwork] = _versioned_network()
        heading: Final[RoamNode] = RoamNode(
            uid="version02",
            id=_V2_ID,
            string="block version02",
            heading=1,
            order=0,
            page=IdObject(id=_PAGE_ID),
            parents=[IdObject(id=_PAGE_ID), IdObject(id=_PARENT_ID)],
        )
        mixed: Final[NodeNetwork] = [heading if n.id == _V2_ID else n for n in network]
        error = all_version_members_share_node_type(mixed)
        assert error is not None
        assert "mixed node types" in error.message
        assert "roam/heading-block" in error.message
        assert "roam/text-block" in error.message
        assert [e.validator for e in validate_version_groups(mixed).errors] == [all_version_members_share_node_type]

    def test_unselected_member_with_children_is_reported(self) -> None:
        """A group is flat: an unselected member heading a subtree fails no_version_member_has_children."""
        network: Final[NodeNetwork] = _versioned_network()
        child: Final[RoamNode] = _block("child0001", 40, 0, [_PAGE_ID, _PARENT_ID, _V1_ID])
        parented: Final[RoamNode] = _block("version01", _V1_ID, 0, [_PAGE_ID, _PARENT_ID], children=[40])
        flattened_out: Final[NodeNetwork] = [*(parented if n.id == _V1_ID else n for n in network), child]
        error = no_version_member_has_children(flattened_out)
        assert error is not None
        assert f"group {_GROUP_ID}: members with children: [{_V1_ID}]" in error.message

    def test_selected_member_with_children_is_reported_too(self) -> None:
        """The rule binds the selected member as well: a versioned block never heads a subtree."""
        network: Final[NodeNetwork] = _versioned_network()
        child: Final[RoamNode] = _block("child0001", 40, 0, [_PAGE_ID, _PARENT_ID, _V3_ID])
        parented: Final[RoamNode] = _block("version03", _V3_ID, 0, [_PAGE_ID, _PARENT_ID], children=[40])
        with_section: Final[NodeNetwork] = [*(parented if n.id == _V3_ID else n for n in network), child]
        error = no_version_member_has_children(with_section)
        assert error is not None
        assert f"[{_V3_ID}]" in error.message
        assert [e.validator for e in validate_version_groups(with_section).errors] == [no_version_member_has_children]

    def test_flatness_failure_blocks_derivation(self) -> None:
        """A network whose version member has children cannot derive groups, nor build a tree."""
        network: Final[NodeNetwork] = _versioned_network()
        child: Final[RoamNode] = _block("child0001", 40, 0, [_PAGE_ID, _PARENT_ID, _V3_ID])
        parented: Final[RoamNode] = _block("version03", _V3_ID, 0, [_PAGE_ID, _PARENT_ID], children=[40])
        with_section: Final[NodeNetwork] = [*(parented if n.id == _V3_ID else n for n in network), child]
        with pytest.raises(ValueError, match="members with children"):
            version_groups_of(with_section)
        with pytest.raises(ValueError, match="members with children"):
            NodeTree.build(root_node=with_section[0], super_network=with_section)

    def test_no_selected_member_is_reported(self) -> None:
        """A group none of whose members any node's children names fails exactly_one_version_selected."""
        error = exactly_one_version_selected(_versioned_network(selected=[]))
        assert error is not None
        assert "0 of 3 members selected" in error.message

    def test_two_selected_members_is_reported(self) -> None:
        """A group two of whose members the parent's children names fails exactly_one_version_selected."""
        error = exactly_one_version_selected(_versioned_network(selected=[_V1_ID, _V3_ID]))
        assert error is not None
        assert "2 of 3 members selected" in error.message


class TestVersionGroupsOf:
    """Tests for deriving VersionGroups from a network."""

    def test_derives_the_group(self) -> None:
        """The reference arrangement yields one group with the right members, selection, and parent."""
        groups: Final[dict[int, VersionGroup]] = version_groups_of(_versioned_network())
        assert set(groups) == {_GROUP_ID}
        group: Final[VersionGroup] = groups[_GROUP_ID]
        assert group.uid == "group0000"
        assert group.member_ids == (_V1_ID, _V2_ID, _V3_ID)
        assert group.selected_id == _V3_ID
        assert group.unselected_ids == (_V1_ID, _V2_ID)
        assert group.parent_id == _PARENT_ID
        assert group.node_type is NodeType.TEXT_BLOCK

    def test_network_without_groups_yields_nothing(self) -> None:
        """A network with no version group derives an empty map."""
        assert version_groups_of([_page([_PARENT_ID]), _block("parent000", _PARENT_ID, 0, [_PAGE_ID])]) == {}

    def test_scope_keeps_groups_touching_it(self) -> None:
        """A group with a member in scope is kept; one with no member in scope is dropped."""
        network: Final[NodeNetwork] = _versioned_network()
        assert set(version_groups_of(network, scope_ids={_V2_ID})) == {_GROUP_ID}
        assert set(version_groups_of(network, scope_ids={_V1_ID, _V2_ID, _V3_ID})) == {_GROUP_ID}
        assert version_groups_of(network, scope_ids={_PAGE_ID, _PARENT_ID}) == {}
        assert version_groups_of(network, scope_ids=set()) == {}

    def test_invalid_network_raises(self) -> None:
        """A network failing validation raises, naming the failure."""
        with pytest.raises(ValueError, match="version group validation failed.*2 of 3 members selected"):
            version_groups_of(_versioned_network(selected=[_V1_ID, _V3_ID]))

    def test_pivot_by_member_id(self) -> None:
        """version_groups_by_member_id maps every member of every group to its group."""
        groups: Final[dict[int, VersionGroup]] = version_groups_of(_versioned_network())
        by_member: Final[dict[int, VersionGroup]] = version_groups_by_member_id(groups)
        assert set(by_member) == {_V1_ID, _V2_ID, _V3_ID}
        assert all(group is groups[_GROUP_ID] for group in by_member.values())

    def test_article0_fixture(self) -> None:
        """The recorded [[Test Article]] 0 network derives block 3.4's group exactly."""
        network: Final[NodeNetwork] = _article0_network()
        by_uid: Final[dict[str, RoamNode]] = {node.uid: node for node in network}
        groups: Final[dict[int, VersionGroup]] = version_groups_of(network)
        assert len(groups) == 1
        group: Final[VersionGroup] = next(iter(groups.values()))
        assert group.uid == _GROUP_UID
        assert group.id == by_uid[_GROUP_UID].id
        assert group.member_ids == tuple(by_uid[uid].id for uid in _VERSION_UIDS)
        assert group.selected_id == by_uid[_SELECTED_UID].id
        assert group.parent_id == by_uid[_PARENT_UID].id
        assert group.node_type is NodeType.TEXT_BLOCK


class TestNodeTreeVersionGroups:
    """Tests for the version-group maps NodeTree.build derives."""

    def test_tree_carries_the_groups_of_its_nodes(self) -> None:
        """A tree whose parent block is versioned exposes the group both ways."""
        network: Final[NodeNetwork] = _versioned_network()
        tree: Final[NodeTree] = NodeTree.build(root_node=network[0], super_network=network)
        assert set(tree.version_groups_by_id) == {_GROUP_ID}
        assert set(tree.version_groups_by_member_id) == {_V1_ID, _V2_ID, _V3_ID}
        assert tree.version_groups_by_member_id[_V1_ID].selected_id == _V3_ID
        # Only the selected version is in the tree; the group is reachable through the maps alone.
        assert {n.id for n in tree.tree_network} == {_PAGE_ID, _PARENT_ID, _V3_ID}

    def test_tree_without_versioned_nodes_has_empty_maps(self) -> None:
        """A tree none of whose nodes is versioned exposes nothing, even when the network holds a group."""
        network: Final[NodeNetwork] = _versioned_network()
        other_page: Final[RoamNode] = RoamNode(uid="page00001", id=50, title="Other", children=[])
        tree: Final[NodeTree] = NodeTree.build(root_node=other_page, super_network=[*network, other_page])
        assert tree.version_groups_by_id == {}
        assert tree.version_groups_by_member_id == {}

    def test_article0_tree(self) -> None:
        """The recorded [[Test Article]] 0 tree exposes block 3.4's group, keyed by every version."""
        network: Final[NodeNetwork] = _article0_network()
        by_uid: Final[dict[str, RoamNode]] = {node.uid: node for node in network}
        tree: Final[NodeTree] = NodeTree.build(root_node=by_uid["L7iQsWlWT"], super_network=network)
        assert set(tree.version_groups_by_id) == {by_uid[_GROUP_UID].id}
        assert set(tree.version_groups_by_member_id) == {by_uid[uid].id for uid in _VERSION_UIDS}
        assert tree.version_groups_by_id[by_uid[_GROUP_UID].id].selected_id == by_uid[_SELECTED_UID].id

    def test_tree_holds_every_member_node(self) -> None:
        """The tree keeps every version node reachable by id, the unselected ones included."""
        network: Final[NodeNetwork] = _versioned_network()
        tree: Final[NodeTree] = NodeTree.build(root_node=network[0], super_network=network)
        assert set(tree.version_members_by_id) == {_V1_ID, _V2_ID, _V3_ID}
        assert tree.version_members_by_id[_V1_ID].uid == "version01"
        # The unselected versions are held here and nowhere else on the tree.
        assert _V1_ID not in tree.id_map
        assert _V3_ID in tree.id_map

    def test_maps_are_excluded_from_dumps(self) -> None:
        """The derived maps never reach a serialized tree, like the other derived maps."""
        network: Final[NodeNetwork] = _versioned_network()
        tree: Final[NodeTree] = NodeTree.build(root_node=network[0], super_network=network)
        dumped: Final[dict[str, object]] = tree.model_dump(mode="json")
        assert "version_groups_by_id" not in dumped
        assert "version_groups_by_member_id" not in dumped
        assert "version_members_by_id" not in dumped
