import copy

from lark import Lark, Transformer
from lark.visitors import Discard

import topside as top


grammar = '''
%import common.LETTER
%import common.DIGIT
%import common.NUMBER
%import common.WS
%ignore WS

document: procedure*
procedure: name ":" step+
name: NAME

step: step_id "." personnel ":" [condition] action deviation*
step_id: NAME_OR_NUMBER
personnel: NAME

action: state_change_action | misc_action

state_change_action: ( "set" | "Set" ) component "to" state
component: NAME
state: NAME

misc_action: SENTENCE

deviation: "-" condition transition
transition: name "." step_id

condition: "[" boolean_expr "]"

waitfor: time "s"
time: NUMBER

boolean_expr: boolean_expr_and ( logic_or boolean_expr_and )*

boolean_expr_and: boolean ( logic_and boolean )*

boolean: waitfor
    | node operator value
    | "(" boolean_expr ")"

logic_and : "and" | "&&" | "AND"
logic_or  : "or" | "||" | "OR"

// TODO(jacob): Add support for tolerance in equality comparison.
node: NAME
value: NUMBER
operator: "<"    -> lt
        | ">"    -> gt
        | "<="   -> le
        | ">="   -> ge
        | "=="   -> eq

NAME: (LETTER | "_") (LETTER | DIGIT | "_" | "-")*
NAME_OR_NUMBER: (LETTER | DIGIT | "_")+
SENTENCE: (LETTER) (LETTER | DIGIT | "_" | " " | ",")*
'''

parser = Lark(grammar, start='document')


class ProcedureTransformer(Transformer):
    """
    Transformer for converting a Lark parse tree to a ProcedureSuite.

    Visits leaf nodes first and only processes a parent node once all of
    its children have been processed. Member functions of this class are
    handlers for the rules of the same names in the grammar described
    above.
    """

    def handle_string(self, orig):
        """
        Utility for processing a generic string in the parse tree.
        """
        (s,) = orig
        return s.value

    def handle_number(self, orig):
        """
        Utility for processing a generic number in the parse tree.
        """
        (n,) = orig
        return float(n)

    # For all of the comparison operators, `data` doesn't contain
    # anything useful; we just match the type of the node to the
    # appropriate comparison class and return.

    def lt(self, data):
        return top.Less

    def gt(self, data):
        return top.Greater

    def le(self, data):
        return top.LessEqual

    def ge(self, data):
        return top.GreaterEqual

    def eq(self, data):
        return top.Equal

    def logic_and(self, data):
        raise Discard()

    def logic_or(self, data):
        raise Discard()

    def boolean(self, data):
        """
        Parses a directly evaluatable boolean value in the parse tree

        `data` is a list of either:
            - three elements, of the form [node, operator, reference]
            - one WaitFor element
            - one boolean_expr element, which was wrapped in parentheses in the
              text
         """

        if len(data) == 3:
            # Must be a [node, operator, reference] type
            comp_class = data[1]
            return comp_class(data[0], data[2])
        elif len(data) == 1 and type(data[0]) == top.WaitFor:
            return data[0]
        elif len(data) == 1:
            # Assume that this is a parenthesized expression
            return data[0]

    def boolean_expr(self, data):
        """
        Process `boolean_expr` nodes in the parse tree.

        `data` is a list of `boolean_expr_and`'s that were interspersed in the
        text with logical OR's.
        """
        if len(data) == 1:
            return data[0]
        else:
            return top.Or(data)

    def boolean_expr_and(self, data):
        """
        Process `boolean_expr_and` nodes in the parse tree.

        `data` is a list of `boolean`'s that were interspersed in the text with
        logical AND's.
        """
        if len(data) == 1:
            return data[0]
        else:
            return top.And(data)

    def waitfor(self, data):
        """
        Process `waitfor` nodes in the parse tree.

        `data` is a list of the form [reference_time]. reference_time is
        in seconds, so we need to convert it to microseconds.
        """
        return top.WaitFor(data[0] * 1e6)

    def condition(self, data):
        """
        Process `condition` nodes in the parse tree.

        `data` is a list of the form [condition].

        NOTE(jacob): We could instead inline the condition node in the
        Lark grammar with a leading `?`, but for now we explicitly
        handle it here for clarity.
        """
        return data[0]

    def transition(self, data):
        """
        Process `transition` nodes in the parse tree.

        `data` is a tuple of the form (procedure, step).
        """
        procedure, step = data
        return top.Transition(procedure, step)

    def action(self, data):
        """
        Process `action` nodes in the parse tree.

        `data` is a list of the form [action].
        """
        return data[0]

    def state_change_action(self, data):
        """
        Process `state_change_action` nodes in the parse tree.

        `data` is a tuple of the form (component, state).
        """
        component, state = data
        return top.StateChangeAction(component, state)

    def misc_action(self, data):
        """
        Process `misc_action` nodes in the parse tree.

        `data` is a list of the form [action].
        """
        return top.MiscAction(data[0])

    def step(self, data):
        """
        Process `step` nodes in the parse tree.

        We can't build the steps themselves yet, since the condition for
        advancing to the next step is an annotation on that next step.
        Instead, we build an intermediate step_info dict and then
        process all of the steps in sequence at the next stage.

        data will look like one of these, depending on if the step has
        an attached entry condition:
            [id, personnel, step entry condition, action, deviation1, deviation2, ...]
            [id, personnel, action, deviation1, deviation2, ...]
        """
        step_info = {}
        step_info['id'] = data[0]
        step_info['personnel'] = data[1]
        step_info['conditions_out'] = []

        if isinstance(data[2], top.Action):  # Step has no attached entry condition
            step_info['condition_in'] = top.Immediate()
            step_info['action'] = data[2]
            deviations = data[3:]
        else:  # Step has an attached entry condition
            step_info['condition_in'] = data[2]
            step_info['action'] = data[3]
            deviations = data[4:]

        for cond, transition in deviations:
            step_info['conditions_out'].append((cond, transition))

        return step_info

    def procedure(self, data):
        """
        Process `procedure` nodes in the parse tree.

        `data` is a list of the form [name, step0, step1, ...], where
        `name` is a string indicating the procedure ID and each `stepN`
        is a step_info dict generated by handling a `step` node.
        """
        name = data[0]
        steps = []

        # We optionally annotate each step with its entry condition (the
        # optional [p1 < 100] or [500s] before the step), and the
        # preceding step needs that information for its condition set.
        # In order to get that, we iterate over the steps in reverse
        # order and keep track of the most recently processed step, which
        # is the "successor" of the next step we will process.

        successor = None
        for step_info in data[-1:0:-1]:
            conditions = copy.deepcopy(step_info['conditions_out'])
            if successor is not None:
                conditions.append((successor['condition_in'],
                                   top.Transition(name, successor['id'])))
            successor = step_info
            new_step = top.ProcedureStep(
                step_info['id'], step_info['action'], conditions, step_info['personnel'])
            steps.insert(0, new_step)

        return top.Procedure(name, steps)

    def document(self, data):
        """
        Process `document` nodes in the parse tree.

        `data` is a list of Procedure objects.
        """
        # TODO(jacob): Add support for parsing ProcedureSuite metadata.
        return top.ProcedureSuite(data)

    node = handle_string
    value = handle_number

    time = handle_number

    deviation = tuple

    component = handle_string
    state = handle_string

    step_id = handle_string
    personnel = handle_string

    name = handle_string
    name_or_number = handle_string


def parse(text):
    """
    Parse a full ProcLang string and return a procedure suite.

    Parameters
    ----------

    text: str
        A string of ProcLang.

    Returns
    -------

    procedure: topside.ProcedureSuite
        A procedure suite containing all of the procedures described in
        the ProcLang string.
    """

    tree = parser.parse(text)
    return ProcedureTransformer().transform(tree)


def parse_from_file(path):
    """
    Parse ProcLang from a file and return a procedure suite.

    Parameters
    ----------

    path: str
        The path to a text file containing a valid ProcLang string.

    Returns
    -------

    procedure: topside.ProcedureSuite
        A procedure suite containing all of the procedures described in
        the ProcLang document.
    """

    with open(path) as f:
        text = f.read()

    tree = parser.parse(text)
    return ProcedureTransformer().transform(tree)
