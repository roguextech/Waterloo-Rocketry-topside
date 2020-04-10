import pytest

import operations_simulator as ops
import operations_simulator.plumbing.plumbing_utils as utils
import operations_simulator.plumbing.exceptions as exceptions


def create_component(s1v1, s1v2, s2v1, s2v2, name, key):
    pc_states = {
        'open': {
            (1, 2, key + '1'): s1v1,
            (2, 1, key + '2'): s1v2
        },
        'closed': {
            (1, 2, key + '1'): s2v1,
            (2, 1, key + '2'): s2v2
        }
    }
    pc_edges = [(1, 2, key + '1'), (2, 1, key + '2')]
    pc = ops.PlumbingComponent(name, pc_states, pc_edges)
    return pc


def two_valve_setup(vAs1_1, vAs1_2, vAs2_1, vAs2_2, vBs1_1, vBs1_2, vBs2_1, vBs2_2):
    pc1 = create_component(vAs1_1, vAs1_2, vAs2_1, vAs2_2, 'valve1', 'A')
    pc2 = create_component(vBs1_1, vBs1_2, vBs2_1, vBs2_2, 'valve2', 'B')

    component_mapping = {
        'valve1': {
            1: 1,
            2: 2
        },
        'valve2': {
            1: 2,
            2: 3
        }
    }

    pressures = {3: 100}
    default_states = {'valve1': 'closed', 'valve2': 'open'}
    plumb = ops.PlumbingEngine(
        {'valve1': pc1, 'valve2': pc2}, component_mapping, pressures, default_states)

    return plumb


def test_empty_graph():
    plumb = ops.PlumbingEngine()

    assert plumb.time_resolution == utils.DEFAULT_TIME_RESOLUTION_MICROS
    assert not list(plumb.plumbing_graph.edges(data=True, keys=True))
    assert not list(plumb.plumbing_graph.nodes(data=True))


def test_open_closed_valves():
    plumb = two_valve_setup(0, 0, 'closed', 'closed', 0, 0, 'closed', 'closed')

    assert plumb.time_resolution == utils.DEFAULT_TIME_RESOLUTION_MICROS
    assert list(plumb.plumbing_graph.edges(data=True, keys=True)) == [
        (1, 2, 'A1', {'FC': 0}),
        (2, 1, 'A2', {'FC': 0}),
        (2, 3, 'B1', {'FC': utils.FC_MAX}),
        (3, 2, 'B2', {'FC': utils.FC_MAX})
    ]
    assert list(plumb.plumbing_graph.nodes(data=True)) == [
        (1, {'pressure': 0}),
        (2, {'pressure': 0}),
        (3, {'pressure': 100})
    ]
    assert plumb.component_dict['valve1'].current_state == 'closed'
    assert plumb.component_dict['valve2'].current_state == 'open'


def test_arbitrary_states():
    plumb = two_valve_setup(0.5, 0.2, 10, 'closed', 0.5, 0.2, 10, 'closed')

    assert plumb.time_resolution == int(utils.s_to_micros(0.2) / utils.DEFAULT_RESOLUTION_SCALE)
    assert list(plumb.plumbing_graph.edges(data=True, keys=True)) == [
        (1, 2, 'A1', {'FC': utils.teq_to_FC(utils.s_to_micros(10))}),
        (2, 1, 'A2', {'FC': 0}),
        (2, 3, 'B1', {'FC': utils.teq_to_FC(utils.s_to_micros(0.5))}),
        (3, 2, 'B2', {'FC': utils.teq_to_FC(utils.s_to_micros(0.2))})
    ]
    assert list(plumb.plumbing_graph.nodes(data=True)) == [
        (1, {'pressure': 0}),
        (2, {'pressure': 0}),
        (3, {'pressure': 100})
    ]
    assert plumb.component_dict['valve1'].current_state == 'closed'
    assert plumb.component_dict['valve2'].current_state == 'open'


def test_load_graph_to_empty():
    plumb0 = two_valve_setup(0.5, 0.2, 10, 'closed', 0.5, 0.2, 10, 'closed')
    pressures = {3: 100}
    default_states = {'valve1': 'closed', 'valve2': 'open'}

    plumb = ops.PlumbingEngine()
    plumb.load_graph(plumb0.component_dict, plumb0.mapping, pressures, default_states)

    assert plumb.time_resolution == int(utils.s_to_micros(0.2) / utils.DEFAULT_RESOLUTION_SCALE)
    assert list(plumb.plumbing_graph.edges(data=True, keys=True)) == [
        (1, 2, 'A1', {'FC': utils.teq_to_FC(utils.s_to_micros(10))}),
        (2, 1, 'A2', {'FC': 0}),
        (2, 3, 'B1', {'FC': utils.teq_to_FC(utils.s_to_micros(0.5))}),
        (3, 2, 'B2', {'FC': utils.teq_to_FC(utils.s_to_micros(0.2))})
    ]
    assert list(plumb.plumbing_graph.nodes(data=True)) == [
        (1, {'pressure': 0}),
        (2, {'pressure': 0}),
        (3, {'pressure': 100})
    ]
    assert plumb.component_dict['valve1'].current_state == 'closed'
    assert plumb.component_dict['valve2'].current_state == 'open'


def test_replace_graph():
    plumb0 = two_valve_setup(0.5, 0.2, 10, 'closed', 0.5, 0.2, 10, 'closed')
    plumb = two_valve_setup(0, 0, 'closed', 'closed', 0, 0, 'closed', 'closed')

    pressures = {3: 100}
    default_states = {'valve1': 'closed', 'valve2': 'open'}
    plumb.load_graph(plumb0.component_dict, plumb0.mapping, pressures, default_states)

    assert plumb.time_resolution == int(utils.s_to_micros(0.2) / utils.DEFAULT_RESOLUTION_SCALE)
    assert list(plumb.plumbing_graph.edges(data=True, keys=True)) == [
        (1, 2, 'A1', {'FC': utils.teq_to_FC(utils.s_to_micros(10))}),
        (2, 1, 'A2', {'FC': 0}),
        (2, 3, 'B1', {'FC': utils.teq_to_FC(utils.s_to_micros(0.5))}),
        (3, 2, 'B2', {'FC': utils.teq_to_FC(utils.s_to_micros(0.2))})
    ]
    assert list(plumb.plumbing_graph.nodes(data=True)) == [
        (1, {'pressure': 0}),
        (2, {'pressure': 0}),
        (3, {'pressure': 100})
    ]
    assert plumb.component_dict['valve1'].current_state == 'closed'
    assert plumb.component_dict['valve2'].current_state == 'open'


def test_new_component_state():
    plumb = two_valve_setup(0.5, 0.2, 10, 'closed', 0.5, 0.2, 10, 'closed')
    plumb.set_component_state('valve1', 'open')

    assert list(plumb.plumbing_graph.edges(data=True, keys=True)) == [
        (1, 2, 'A1', {'FC': utils.teq_to_FC(utils.s_to_micros(0.5))}),
        (2, 1, 'A2', {'FC': utils.teq_to_FC(utils.s_to_micros(0.2))}),
        (2, 3, 'B1', {'FC': utils.teq_to_FC(utils.s_to_micros(0.5))}),
        (3, 2, 'B2', {'FC': utils.teq_to_FC(utils.s_to_micros(0.2))})
    ]
    assert plumb.component_dict['valve1'].current_state == 'open'
    assert plumb.component_dict['valve2'].current_state == 'open'


def test_missing_component():
    wrong_component_name = 'potato'
    pc1 = create_component(0, 0, 0, 0, 'valve1', 'A')
    pc2 = create_component(0, 0, 0, 0, 'valve2', 'B')

    component_mapping = {
        'valve1': {
            1: 1,
            2: 2
        },
        'valve2': {
            1: 2,
            2: 3
        }
    }

    pressures = {3: 100}
    default_states = {'valve1': 'closed', 'valve2': 'open'}
    with pytest.raises(exceptions.MissingInputError):
        plumb = ops.PlumbingEngine(
            {wrong_component_name: pc1, 'valve2': pc2}, component_mapping, pressures, default_states)


def test_wrong_node_mapping():
    # The node name should be 1.
    wrong_node_name = 4
    pc1 = create_component(0, 0, 0, 0, 'valve1', 'A')
    pc2 = create_component(0, 0, 0, 0, 'valve2', 'B')

    component_mapping = {
        'valve1': {
            wrong_node_name: 1,
            2: 2
        },
        'valve2': {
            1: 2,
            2: 3
        }
    }

    pressures = {3: 100}
    default_states = {'valve1': 'closed', 'valve2': 'open'}
    with pytest.raises(exceptions.MissingInputError):
        plumb = ops.PlumbingEngine(
            {'valve1': pc1, 'valve2': pc2}, component_mapping, pressures, default_states)


def test_missing_node_pressure():
    wrong_node_name = 4
    pc1 = create_component(0, 0, 0, 0, 'valve1', 'A')
    pc2 = create_component(0, 0, 0, 0, 'valve2', 'B')

    component_mapping = {
        'valve1': {
            1: 1,
            2: 2
        },
        'valve2': {
            1: 2,
            2: 3
        }
    }

    pressures = {wrong_node_name: 100}
    default_states = {'valve1': 'closed', 'valve2': 'open'}
    with pytest.raises(exceptions.MissingInputError):
        plumb = ops.PlumbingEngine(
            {'valve1': pc1, 'valve2': pc2}, component_mapping, pressures, default_states)


def test_missing_initial_state():
    wrong_component_name = 'potato'
    pc1 = create_component(0, 0, 0, 0, 'valve1', 'A')
    pc2 = create_component(0, 0, 0, 0, 'valve2', 'B')

    component_mapping = {
        'valve1': {
            1: 1,
            2: 2
        },
        'valve2': {
            1: 2,
            2: 3
        }
    }

    pressures = {3: 100}
    default_states = {wrong_component_name: 'closed', 'valve2': 'open'}
    with pytest.raises(exceptions.MissingInputError):
        plumb = ops.PlumbingEngine(
            {'valve1': pc1, 'valve2': pc2}, component_mapping, pressures, default_states)


def test_set_component_wrong_state_name():
    wrong_state_name = 'potato'
    plumb = two_valve_setup(0.5, 0.2, 10, 'closed', 0.5, 0.2, 10, 'closed')
    with pytest.raises(exceptions.MissingInputError):
        plumb.set_component_state('valve1', wrong_state_name)


def test_set_component_wrong_component_name():
    wrong_component_name = 'potato'
    plumb = two_valve_setup(0.5, 0.2, 10, 'closed', 0.5, 0.2, 10, 'closed')
    with pytest.raises(exceptions.MissingInputError):
        plumb.set_component_state(wrong_component_name, 'open')