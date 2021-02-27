import datetime
import threading
import weakref

from lepl import *
from lepl.matchers.support import function_matcher
from lepl.matchers.derived import UnsignedEFloat

import sqlalchemy.sql.expression as sa_exp
import sqlalchemy.sql.functions as sa_functions
import sqlalchemy.types as sa_types

import ibe.lib.formats as formats
import ibe.lib.utils as utils

# == AST nodes ========
#
# AST nodes are able to convert themselves to sqlalchemy expressions.
# They can also be asked for the set of columns referenced in their
# (sub)-trees.

class SqlAstNode(List):
    def extract_cols(self):
        """Returns a set containing all column references in the AST
        rooted at this node.
        """
        return set.union(*(n.extract_cols() for n in self if isinstance(n, SqlAstNode)))

    def build(self, table, sa_table):
        """Builds a sqlalchemy expression corresponding to the AST
        rooted at this node.
        """
        raise NotImplementedError()

    def render(self, table):
        """Returns an sqlite compatible string representation of this AST node.
        """
        raise NotImplementedError()

# -- Literals and column references --------
_empty_set = set()

class SqlNumericLiteral(SqlAstNode):
    def build(self, table, sa_table):
        if isinstance(self[0], basestring):
            if any(c in self[0] for c in '.eE'):
                return sa_exp.literal(float(self[0]), sa_types.Float())
            else:
                return sa_exp.literal(long(self[0]), sa_types.Integer())
        raise RuntimeError("SqlNumericLiteral not parsed correctly!")
    def extract_cols(self): return _empty_set
    def render(self, table): return self[0]

class SqlStringLiteral(SqlAstNode):
    def build(self, table, sa_table):
        if isinstance(self[0], basestring):
            return sa_exp.literal(self[0], sa_types.String())
        raise RuntimeError("SqlStringLiteral not parsed correctly!")
    def extract_cols(self): return _empty_set
    def render(self, table): return ''.join(["'", self[0], "'"])

class SqlTimestampLiteral(SqlAstNode):
    def build(self, table, sa_table):
        if isinstance(self[0], basestring):
            dt = datetime.datetime.strptime(self[0], "%Y-%m-%d %H:%M:%S");
            return sa_exp.literal(dt, sa_types.DateTime())
        raise RuntimeError("SqlTimestampLiteral not parsed correctly!")
    def extract_cols(self): return _empty_set
    def render(self, table): return ''.join(["DATETIME('", self[0], "')"])

class SqlNull(SqlAstNode):
    def build(self, table, sa_table): return sa_exp.null()
    def extract_cols(self): return _empty_set
    def render(self, table): return "NULL"

class SqlNow(SqlAstNode):
    def build(self, table, sa_table): return sa_functions.current_timestamp()
    def extract_cols(self): return _empty_set
    def render(self, table): return "CURRENT_TIMESTAMP"

class SqlColumnReference(SqlAstNode):
    def build(self, table, sa_table):
        sa_table = sa_table if sa_table is not None else table.table()
        name = self[0]
        if name not in table:
            raise RuntimeError(str.format(
                'Column {0} referenced in WHERE clause does not exist', name))
        c = table[name]
        if c.constant:
            return sa_exp.literal(c.const_val, c.type.get(formats.SQLALCHEMY))
        else:
            dbname = table[name].dbname
            if dbname not in sa_table.c:
                raise RuntimeError(str.format(
                    'Column {0} referenced in WHERE clause does not exist', name))
            return sa_table.c[dbname]

    def extract_cols(self): return set([self[0]])
    def render(self, table):
        name = self[0]
        if name not in table:
	    print " ---------------- "
	    print name
            raise RuntimeError(str.format(
                'Column {0} referenced in WHERE clause does not exist', name))
        c = table[name]
        if c.constant:
            return c.type.to_ascii(c.const_val)
        else:
            return c.dbname

# -- Unary minus --------
class SqlUnaryMinus(SqlAstNode):
    def build(self, table, sa_table): return -1*self[0].build(table, sa_table)
    def render(self, table): return '-' + self[0].render(table)

# -- Binary arithmetic operators --------
class SqlAdd(SqlAstNode):
    def build(self, table, sa_table): return self[0].build(table, sa_table).op('+')(self[1].build(table, sa_table))
    def render(self, table): return ''.join(['(', self[0].render(table), ' + ', self[1].render(table), ')'])

class SqlSubtract(SqlAstNode):
    def build(self, table, sa_table): return self[0].build(table, sa_table).op('-')(self[1].build(table, sa_table))
    def render(self, table): return ''.join(['(', self[0].render(table), ' - ', self[1].render(table), ')'])

class SqlMultiply(SqlAstNode):
    def build(self, table, sa_table): return self[0].build(table, sa_table).op('*')(self[1].build(table, sa_table))
    def render(self, table): return ''.join(['(', self[0].render(table), ' * ', self[1].render(table), ')'])

class SqlDivide(SqlAstNode):
    def build(self, table, sa_table): return self[0].build(table, sa_table).op('/')(self[1].build(table, sa_table))
    def render(self, table): return ''.join(['(', self[0].render(table), ' / ', self[1].render(table), ')'])


# -- Binary string operators --------
class SqlConcat(SqlAstNode):
    def build(self, table, sa_table): return self[0].build(table, sa_table).concat(self[1].build(table, sa_table))
    def render(self, table): return ''.join(['(', self[0].render(table), ' || ', self[1].render(table), ')'])

# -- Binary comparison operators --------
class SqlEqualPred(SqlAstNode):
    def build(self, table, sa_table): return self[0].build(table, sa_table) == self[1].build(table, sa_table)
    def render(self, table): return ''.join(['(', self[0].render(table), ' == ', self[1].render(table), ')'])

class SqlNotEqualPred(SqlAstNode):
    def build(self, table, sa_table): return self[0].build(table, sa_table) != self[1].build(table, sa_table)
    def render(self, table): return ''.join(['(', self[0].render(table), ' != ', self[1].render(table), ')'])

class SqlLessThanPred(SqlAstNode):
    def build(self, table, sa_table): return self[0].build(table, sa_table) < self[1].build(table, sa_table)
    def render(self, table): return ''.join(['(', self[0].render(table), ' < ', self[1].render(table), ')'])

class SqlLessThanOrEqualPred(SqlAstNode):
    def build(self, table, sa_table): return self[0].build(table, sa_table) <= self[1].build(table, sa_table)
    def render(self, table): return ''.join(['(', self[0].render(table), ' <= ', self[1].render(table), ')'])

class SqlGreaterThanPred(SqlAstNode):
    def build(self, table, sa_table): return self[0].build(table, sa_table) > self[1].build(table, sa_table)
    def render(self, table): return ''.join(['(', self[0].render(table), ' > ', self[1].render(table), ')'])

class SqlGreaterThanOrEqualPred(SqlAstNode):
    def build(self, table, sa_table): return self[0].build(table, sa_table) >= self[1].build(table, sa_table)
    def render(self, table): return ''.join(['(', self[0].render(table), ' >= ', self[1].render(table), ')'])


# -- [NOT] BETWEEN, IN, LIKE, IS [NOT] NULL
class SqlBetweenPred(SqlAstNode):
    def build(self, table, sa_table):
        expr = self[0].build(table, sa_table).between(self[2].build(table, sa_table), self[3].build(table, sa_table))
        if self[1]:
            expr = sa_exp.not_(expr)
        return expr
    def render(self, table):
        return ''.join(['(',
                        self[0].render(table),
                        ' NOT' if self[1] else '',
                        ' BETWEEN ',
                        self[2].render(table),
                        ' AND ',
                        self[3].render(table),
                        ')'])

class SqlValueList(SqlAstNode):
    def build(self, table, sa_table):
        res = []
        for node in self:
            res.append(node.build(table, sa_table))
        return res
    def render(self, table):
        return ''.join(['(', ', '.join([n.render(table) for n in self]), ')'])

class SqlInPred(SqlAstNode):
    def build(self, table, sa_table):
        expr = self[0].build(table, sa_table).in_(self[2].build(table, sa_table))
        if self[1]:
            expr = sa_exp.not_(expr)
        return expr
    def render(self, table):
        return ''.join(['(',
                        self[0].render(table),
                        ' NOT' if self[1] else '',
                        ' IN ',
                        self[2].render(table),
                        ')'])

class SqlLikePred(SqlAstNode):
    def build(self, table, sa_table):
        esc = self[3].build(table, sa_table) if len(self) > 3 else None
        expr = self[0].build(table, sa_table).like(self[2].build(table, sa_table), esc)
        if self[1]:
            expr = sa_exp.not_(expr)
        return expr
    def render(self, table):
        return ''.join(['(',
                        self[0].render(table),
                        ' NOT' if self[1] else '',
                        ' LIKE ',
                        self[2].render(table),
                        ' ' if len(self) > 3 else '',
                        self[3].render(table) if len(self) > 3 else '',
                        ')'])

class SqlNullPred(SqlAstNode):
    def build(self, table, sa_table):
        if self[1]:
            return self[0].build(table, sa_table) != sa_exp.null()
        return self[0].build(table, sa_table) == sa_exp.null()
    def render(self, table):
        if self[1]:
            return self[0].render(table) + ' IS NOT NULL'
        return self[0].render(table) + ' IS NULL'


# -- AND, OR, NOT --------
class SqlNot(SqlAstNode):
    def build(self, table, sa_table): return sa_exp.not_(self[0].build(table, sa_table))
    def render(self, table): return 'NOT ' + self[0].render(table)

class SqlAnd(SqlAstNode):
    def build(self, table, sa_table): return sa_exp.and_(self[0].build(table, sa_table), self[1].build(table, sa_table))
    def render(self, table): return ''.join(['(', self[0].render(table), ' AND ', self[1].render(table), ')'])

class SqlOr(SqlAstNode):
    def build(self, table, sa_table): return sa_exp.or_(self[0].build(table, sa_table), self[1].build(table, sa_table))
    def render(self, table): return ''.join(['(', self[0].render(table), ' OR ', self[1].render(table), ')'])


# == Helpers ========

def _escape_decoder(s):
    """Decodes an escape sequence in a string.
    """
    if not isinstance(s, unicode):
        s = unicode(s, 'utf-8')
    return s.decode('unicode_escape')

@function_matcher
def _EmptyWithReturn(support, stream):
    """Always matches, consumes no input, and returns None.
    """
    return ([None], stream)


# == Parser creation ========

def make_parser(trace=False):
    """Creates and returns a parser for SQL WHERE clauses. The parser
    implements a subset of the SQL92 grammar for WHERE clauses.

    Notably missing are CAST expressions, SUBSTRING and TRIM support,
    and mathematical function calls.

    The parser is implemented using the lepl package. Although lepl
    does include facilities for defining tokens and lexing, they are
    not currently used. The reason is that the restricted regular
    expressions available for defining tokens do not seem to be powerful
    enough to describe a string literal with escapes.

    Writing a hand-coded lexer and then using a lepl parser over the
    resulting token stream should improve speed by quite a bit; this
    is left as future work.
    """
    ctx_mgr = TraceVariables if trace else utils.NoopContextMgr

    with ctx_mgr():
        left_paren = Drop('(')
        right_paren = Drop(')')
        quote = Drop("'")
        comma = Drop(',')

        plus = Drop('+')
        minus = Drop('-')
        asterisk = Drop('*')
        solidus = Drop('/')

        concat = Drop('||')

        eq = Drop('=')
        ne = (Drop('!=') | Drop('<>'))
        lte = Drop('<=')
        lt = Drop('<')
        gte = Drop('>=')
        gt = Drop('>')

        ows = Drop(Whitespace()[:])
        ws = Drop(Whitespace()[1:])

        # keywords
        AND = DfaRegexp('[Aa][Nn][Dd]')
        OR = DfaRegexp('[Oo][Rr]')
        IN = DfaRegexp('[Ii][Nn]')
        IS = DfaRegexp('[Ii][Ss]')
        NOT = DfaRegexp('[Nn][Oo][Tt]')
        NULL = DfaRegexp('[Nn][Uu][Ll][Ll]')
        LIKE = DfaRegexp('[Ll][Ii][Kk][Ee]')
        BETWEEN = DfaRegexp('[Bb][Ee][Tt][Ww][Ee][Ee][Nn]')
        ESCAPE = DfaRegexp('[Ee][Ss][Cc][Aa][Pp][Ee]')
        TIMESTAMP = DfaRegexp('[Tt][Ii][Mm][Ee][Ss][Tt][Aa][Mm][Pp]')

        # literals and column references
        numeric_literal = Real() > SqlNumericLiteral
        _unicode_escape = ('\\u' + Digit()[2:4,...]) >> _escape_decoder
        _regular_escape = ('\\' + Any("'bfnrt/\\")) >> _escape_decoder
        _escape = (_unicode_escape | _regular_escape)
        character_string_literal = (quote & (AnyBut("\\'") | _escape)[...] & quote) > SqlStringLiteral
        _timestamp_string = DfaRegexp('[0-9][0-9][0-9][0-9]\-[0-9][0-9]\-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]')
        timestamp_literal = (Drop(TIMESTAMP) & ws & quote & _timestamp_string & quote) > SqlTimestampLiteral
        column_reference = DfaRegexp('[A-Za-z_][A-Za-z0-9_]*') > SqlColumnReference

        # value expression
        value_expression_primary = Delayed()

        _unary_minus_expr = (minus & ows & value_expression_primary) > SqlUnaryMinus
        _unary_plus_expr = plus & ows & value_expression_primary
        factor = \
               _unary_plus_expr \
             | _unary_minus_expr \
             | value_expression_primary

        term = Delayed()
        _multiply_expr = (factor & ows & asterisk & ows & term) > SqlMultiply
        _divide_expr = (factor & ows & solidus & ows & term) > SqlDivide
        term += \
              factor \
            | _multiply_expr \
            | _divide_expr

        numeric_value_expression = Delayed()
        _add_expr = (term & ows & plus & ows & numeric_value_expression) > SqlAdd
        _subtract_expr = (term & ows & minus & ows & numeric_value_expression) > SqlSubtract
        numeric_value_expression += \
              term \
            | _add_expr \
            | _subtract_expr

        string_value_expression = Delayed()
        _concat_expr = (value_expression_primary & ows & concat & ows & string_value_expression) > SqlConcat
        string_value_expression += \
              _concat_expr \
            | value_expression_primary

        value_expression = \
              numeric_value_expression \
            | string_value_expression

        value_expression_primary += \
              numeric_literal \
            | character_string_literal \
            | timestamp_literal \
            | column_reference \
            | left_paren & ows & value_expression & ows & right_paren

        null_specification = Drop(NULL) > SqlNull

        row_value_constructor = \
              value_expression \
            | null_specification

        # predicates
        _eq_pred = row_value_constructor & ows & eq & ows & row_value_constructor > SqlEqualPred
        _ne_pred = row_value_constructor & ows & ne & ows & row_value_constructor > SqlNotEqualPred
        _lt_pred = row_value_constructor & ows & lt & ows & row_value_constructor > SqlLessThanPred
        _lte_pred = row_value_constructor & ows & lte & ows & row_value_constructor > SqlLessThanOrEqualPred
        _gt_pred = row_value_constructor & ows & gt & ows & row_value_constructor > SqlGreaterThanPred
        _gte_pred = row_value_constructor & ows & gte & ows & row_value_constructor > SqlGreaterThanOrEqualPred

        comparison_predicate = \
              _eq_pred \
            | _ne_pred \
            | _lte_pred \
            | _lt_pred \
            | _gte_pred \
            | _gt_pred

        _opt_not = ((NOT & ws) | _EmptyWithReturn()) >> (lambda x: x is not None)

        between_predicate = (row_value_constructor & ws & _opt_not & Drop(BETWEEN) & ws &
                             row_value_constructor & ws & Drop(AND) & ws & row_value_constructor) > SqlBetweenPred

        in_value_list = value_expression[:, (ows & comma & ows)] > SqlValueList

        in_predicate = (row_value_constructor & ws & _opt_not & Drop(IN) & ws &
                        left_paren & ows & in_value_list & ows & right_paren) > SqlInPred

        like_predicate = (string_value_expression & ws & _opt_not & Drop(LIKE) & ws &
                          string_value_expression & Optional(Drop(ESCAPE) & ws & string_value_expression)) > SqlLikePred

        null_predicate = (row_value_constructor & ws & Drop(IS) & ws & _opt_not & Drop(NULL)) > SqlNullPred

        predicate = \
              comparison_predicate \
            | between_predicate \
            | in_predicate \
            | like_predicate \
            | null_predicate

        # search condition
        search_condition = Delayed()

        boolean_primary = \
              predicate \
            | left_paren & ows & search_condition & ows & right_paren

        _bool_not = (Drop(NOT) & ws & boolean_primary) > SqlNot
        boolean_factor = \
              _bool_not \
            | boolean_primary

        boolean_term = Delayed()
        _and = (boolean_factor & ws & Drop(AND) & ws & boolean_term) > SqlAnd
        boolean_term += \
              _and \
            | boolean_factor

        _or = (boolean_term & ws & Drop(OR) & ws & search_condition) > SqlOr
        search_condition += \
              _or \
            | boolean_term

        parser = ows & search_condition & ows & Eos()

    # In conjunction, these two configuration options give >10x speedup
    # versus .config.default() on several sample WHERE clauses, hence
    # they are always on.
    parser.config.auto_memoize(full=True)
    parser.config.compile_to_nfa(force=True)
    # The following explicitly turns off the lexer to avoid (harmless) log
    # messages about the lexer rewriting pass not finding any token definitions.
    parser.config.no_lexer()
    return parser


class ParserPool(object):
    """Maintains a SQL parser per program thread, just in case LEPL
    parsers aren't thread-safe (which was not clear to me from the docs).
    """
    def __init__(self):
        self._parse = threading.local()
        self._all_parse = set()

    def __call__(self, *args):
        try:
            p = self._parse.current()
            if p:
                return p(*args)
        except AttributeError:
            pass
        p = make_parser().get_parse()
        self._parse.current = weakref.ref(p)
        self._all_parse.add(p)
        return p(*args)

    def clear(self):
        self._all_parse.clear()

    def clear_local(self):
        if hasattr(self._parse, 'current'):
            p = self._parse.current()
            self._all_parse.discard(p)
            del self._parse.current


def cvmap_to_ast(cvmap):
    """Builds a WHERE clause abstract syntax tree for the given row id
    specification.
    """
    ast = None
    for col_name in cvmap.keys():
        c = SqlColumnReference((col_name,))
        val = cvmap[col_name]
        if val is None:
            pred = SqlNullPred((c, False))
        else:
            if isinstance(val, basestring):
                v = SqlStringLiteral((val,))
            else:
                v = SqlNumericLiteral((repr(val),))
            pred = SqlEqualPred((c, v))
        if ast is None:
            ast = pred
        else:
            ast = SqlAnd((pred, ast))
    return ast

