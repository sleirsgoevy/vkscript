import vkscript.lexer as lexer

class Node:
    def __init__(self):
        raise NotImplementedError
    def __repr__(self):
        return repr(type(self))[8:-2]+'('+', '.join(k+'='+repr(v) for k, v in self.__dict__.items())+')'

class CodeBlock(Node):
    def __init__(self, code):
        self.children = []
        cur = self.children
        prev_if = []
        idx = 0
        while idx < len(code.value):
            if isinstance(code.value[idx], lexer.Identifier):
                x = code.value[idx].value
            else:
                x = None
#           print(code.value[idx])
            if x != 'else' and cur is self.children: prev_if.clear()
            if x in ('if', 'while'):
                if len(code.value) <= idx + 1 or not isinstance(code.value[idx + 1], lexer.EnclosedParens):
                    raise lexer.VKSyntaxError.fromLexem(code.value[min(len(code.value)-1, idx+1)], i+': expected parenthesis')
                inner = [(AssignExpr, [code.value[idx+1]])]
                if x == 'if': prev_if.append(inner)
                cur.append((If if x == 'if' else While, inner))
                cur = inner
                idx += 2
            elif x == 'else':
                if not prev_if:
                    raise lexer.VKSyntaxError.fromLexem(code.value[idx], '`else\' without `if\'')
                prev = prev_if.pop()
                inner = []
                prev.append((Else, inner))
                cur = inner
                idx += 1
            elif isinstance(code.value[idx], lexer.EnclosedCurly):
                cur.append((CodeBlock, code.value[idx]))
                idx += 1
                cur = self.children
            else:
                i = idx
                while i < len(code.value) and (not isinstance(code.value[i], lexer.Operator) or code.value[i].value != ';'):
                    i += 1
                if i == len(code.value):
                    raise lexer.VKSyntaxError.fromLexem(code.value[-1], 'expected `;\'')
                if x == 'var':
                    cur.append((VarDecl, code.value[idx+1:i]))
                elif x == 'delete':
                    cur.append((Delete, code.value[idx+1:i]))
                elif x == 'return':
                    cur.append((Return, code.value[idx+1:i]))
                elif idx != i:
                    cur.append((DropExpr, code.value[idx:i]))
                idx = i + 1
                cur = self.children
    def compile(self, popvars=True):
        ans = []
        if popvars: ans.append(('.enter'))
        for i in self.children:
            ans.append(('.recur', i))
        if popvars: ans.append(('.leave'))
        return ans

class IfElseWhile(Node):
    def __init__(self, data):
        self.children = data

class If(IfElseWhile):
    def compile(self):
        ans = [('.recur', self.children[0]), '.cgoto', '.enter']
        else_blk = None
        if isinstance(self.children[-1], Else):
            else_blk = self.children.pop()
        for i in self.children[1:]:
            ans.append(('.recur', i))
        ans.append('.leave')
        if else_blk != None:
            ans.extend(('.goto', '.clabel', '.enter', ('.recur', else_blk), '.leave', '.label'))
        else:
            ans.append('.clabel')
        return ans

class Else(IfElseWhile):
    def compile(self):
        ans = []
        for i in self.children:
            ans.append(('.recur', i))
        return ans
        
class While(IfElseWhile):
    def compile(self):
        ans = ['.comefrom', ('.recur', self.children[0]), '.cgoto', '.enter']
        for i in self.children[1:]:
            ans.append(('.recur', i))
        ans.extend(('.leave', '.cflabel', '.clabel'))
        return ans

class VarDecl(Node):
    def __init__(self, data):
        self.varnames = []
        self.children = []
        idx = 0
        while True:
            if idx >= len(data) or not isinstance(data[idx], lexer.Identifier):
                raise lexer.VKSyntaxError.fromLexem(data[min(data.length-1, idx)], 'expected identifier')
            name = data[idx].value
            if name in ('if', 'while', 'var', 'delete', 'return', 'API'):
                raise lexer.VKSyntaxError.fromLexem(data[idx], '`'+name+'\' unexpected')
            idx += 1
            if idx < len(data) and (not isinstance(data[idx], lexer.Operator) or data[idx].value not in (',', '=')):
                raise lexer.VKSyntaxError.fromLexem(data[idx], '`=\' expected')
            if idx == len(data) or data[idx].value == ',':
                self.varnames.append(name)
                self.children.append(None)
                idx += 1
            else:
                idx += 1
                idx0 = idx
                while idx < len(data) and (not isinstance(data[idx], lexer.Operator) or data[idx].value != ','):
                    idx += 1
                self.varnames.append(name)
                self.children.append((AssignExpr, data[idx0:idx]))
            if idx >= len(data): break
    def compile(self):
        ans = []
        for k, v in zip(self.varnames, self.children):
            if v == None:
                ans.append(('.declvar', k))
            else:
                ans.append(('.recur', v))
                ans.append(('.popvar', k))
        return ans

class DelRet(Node):
    def __init__(self, data):
        self.children = [(AssignExpr, data)]

class Delete(DelRet):
    def compile(self):
        if isinstance(self.children[0], AttrGet):
            return [('.recur', self.children[0].children[0]), ('delattr', self.children[0].attr), 'update']
        elif isinstance(self.children[0], Variable):
            return [('.delvar', self.children[0])]
        else:
            raise lexer.VKSyntaxError.fromLexem(self.children[0], 'expected identifier')
        
class Return(DelRet):
    def compile(self):
        return [('.recur', self.children[0]), 'return']

class Expression(Node): pass

class BinaryOpExpr(Expression):
    def compile(self):
        return [('.recur', self.children[0]), ('.recur', self.children[1]), ('binop', self.op)]

class LeftAssocExpr(BinaryOpExpr):
    def __init__(self, data):
        i = len(data) - 1
        while i > 0:
            if isinstance(data[i], lexer.Operator) and data[i].value in self.OPS and not isinstance(data[i - 1], lexer.Operator):
                self.op = data[i].value
                self.children = [(self, data[:i]), (self.NEXT, data[i+1:])]
                break
            i -= 1
        else:
            self.op = None
            self.replace = (self.NEXT, data)

class RightAssocExpr(BinaryOpExpr):
    def __init__(self, data):
        i = 1
        while i < len(data):
            if isinstance(data[i], lexer.Operator) and data[i].value in self.OPS and not isinstance(data[i - 1], lexer.Operator):
                self.op = data[i].value
                self.children = [(self.NEXT, data[:i]), (self, data[i+1:])]
                break
            i += 1
        else:
            self.op = None
            self.replace = (self.NEXT, data)

class LeafExpr(Expression):
    def __init__(self, data):
        if len(data) != 1:
            if not data:
                raise lexer.VKSyntaxError(None, -1, -1, 'empty expression')
            raise lexer.VKSyntaxError.fromLexem(data[1], 'invalid expression')
        elif isinstance(data[0], lexer.Operator):
            raise lexer.VKSyntaxError.fromLexem(data[0], 'invalid expression')
        elif isinstance(data[0], lexer.Identifier):
            if data[0].value in ('if', 'while', 'var', 'delete', 'return', 'API'):
                raise lexer.VKSyntaxError.fromLexem(data[0], 'expected identifier, got `'+data[0].value+'\'')
            elif data[0].value.isnumeric():
                self.replace = (Literal, int(data[0].value))
            elif data[0].value[0].isnumeric():
                raise lexer.VKSyntaxError.fromLexem(data[0], 'invalid number `'+data[0].value+'\'')
            else:
                self.replace = (Variable, data[0].value)
        elif isinstance(data[0], lexer.StringLiteral):
            self.replace = (Literal, data[0].value)
        elif isinstance(data[0], lexer.EnclosedParens):
            self.replace = (AssignExpr, data[0].value)
        elif isinstance(data[0], lexer.EnclosedSquare):
            self.replace = (ArrayExpr, data[0])
        elif isinstance(data[0], lexer.EnclosedCurly):
            self.replace = (ObjectExpr, data[0])
        else:
            assert False, data

class AtomicExpr(Expression):
    @staticmethod
    def _get_dotted(data):
        if not data or not (all(isinstance(i, lexer.Identifier) for i in data[::2]) and all(isinstance(i, lexer.Operator) and i.value == '.' for i in data[1::2])): return None
        return ''.join(i.value for i in data)
    def __init__(self, data):
        if not data:
            raise lexer.VKSyntaxError(None, -1, -1, 'empty expression')
        elif len(data) == 1:
            self.replace = (LeafExpr, data)
        elif isinstance(data[-1], lexer.EnclosedParens):
            args = data.pop()
            if isinstance(data[0], lexer.Identifier) and data[0].value == 'API':
                name = self._get_dotted(data)
                if name == None:
                    raise lexer.VKSyntaxError.fromLexem(args, 'invalid API call')
                self.replace = (APICallExpr, name, args)
            elif len(data) == 1 and isinstance(data[0], lexer.Identifier) and data[0].value in ('parseInt', 'parseDouble'):
                self.replace = (BuiltinCallExpr, data[0].value, args)
            elif len(data) <= 2 or not isinstance(data[-2], lexer.Operator) or data[-2].value != '.' or not isinstance(data[-1], lexer.Identifier) or data[-1].value[0].isnumeric():
                raise lexer.VKSyntaxError.fromLexem(args, 'invalid method call')
            else:
                self.replace = (MethodCallExpr, data[:-2], data[-1].value, args)
        elif isinstance(data[-1], lexer.EnclosedSquare):
            if not data[-1].value:
                raise lexer.VKSyntaxError.fromLexem(data[-1], 'empty array subscription')
            self.replace = (ArrayGetExpr, data[:-1], data[-1].value)
        elif isinstance(data[-1], lexer.Identifier) and isinstance(data[-2], lexer.Operator) and data[-2].value in ('.', '@.') and not data[-1].value[0].isnumeric():
            if data[-2].value == '.':
                self.replace = (AttrGetExpr, data[:-2], data[-1].value)
            else:
                self.replace = (FilterExpr, data[:-2], data[-1].value)
        else:
            name = self._get_dotted(data)
            val = None
            if name != None:
                try: val = float(name)
                except ValueError: pass
            if val == None:
                raise lexer.VKSyntaxError.fromLexem(data[0], 'invalid expression')
            self.replace = (Literal, val)

class UnaryOpExpr(Expression):
    def __init__(self, data):
        if not data:
            raise lexer.VKSyntaxError(None, -1, -1, 'empty expression')
        elif isinstance(data[0], lexer.Operator) and data[0].value in self.OPS:
            if data[0].value == '-':
                name = AtomicExpr._get_dotted(data[1:])
                val = None
                if name != None:
                    if name.isnumeric(): val = int(name)
                    else:
                        try: val = float(name)
                        except ValueError: pass
                if val != None:
                    self.replace = (Literal, -val)
                    return
            self.op = data[0].value
            self.children = [(self, data[1:])]
        else:
            self.op = None
            self.replace = (self.NEXT, data)
    def compile(self):
        return [('.recur', self.children[0]), ('unaryop', self.op)]
    OPS = ['!', '~', '-']
    NEXT = AtomicExpr

class MulOpExpr(LeftAssocExpr):
    OPS = ['*', '/', '%']
    NEXT = UnaryOpExpr

class AddSubExpr(LeftAssocExpr):
    OPS = ['+', '-']
    NEXT = MulOpExpr

class ShiftExpr(LeftAssocExpr):
    OPS = ['<<', '>>']
    NEXT = AddSubExpr

class CompareExpr(LeftAssocExpr):
    OPS = ['>', '>=', '<', '<=']
    NEXT = ShiftExpr

class EqOpExpr(LeftAssocExpr):
    OPS = ['==', '!=']
    NEXT = CompareExpr

class BitAndExpr(LeftAssocExpr):
    OPS = ['&']
    NEXT = EqOpExpr

class BitOrExpr(LeftAssocExpr):
    OPS = ['|']
    NEXT = BitAndExpr

class LogicalExpr(LeftAssocExpr):
    def compile(self):
        return [('.recur', self.children[0]), ('.cgoto', ('and' if self.op == '&&' else 'or')), ('.recur', self.children[1]), '.clabel']

class AndExpr(LogicalExpr):
    OPS = ['&&']
    NEXT = BitOrExpr

class OrExpr(LogicalExpr):
    OPS = ['||']
    NEXT = AndExpr

class TernaryOpExpr(Expression):
    def __init__(self, data):
        i = 0
        while i < len(data):
            if isinstance(data[i], lexer.EnclosedTernary):
                self.children = [(OrExpr, data[:i]), (AssignExpr, data[i].value), (TernaryOpExpr, data[i+1:])]
                break
            i += 1
        else: self.replace = (OrExpr, data)
    def compile(self):
        return [('.recur', self.children[0]), '.cgoto', ('.recur', self.children[1]), '.goto', '.clabel', ('.recur', self.children[2]), '.label']

class AssignExpr(RightAssocExpr):
    OPS = ['=']
    NEXT = TernaryOpExpr
    def __init__(self, data):
        super().__init__(data)
        if self.op == '=' and AtomicExpr._get_dotted(self.children[0][1]) == None:
            raise lexer.VKSyntaxError.fromLexem(self.children[0][1][0], 'non-variable in assignment')
    def compile(self):
        if isinstance(self.children[0], AttrGetExpr):
            return [('.recur', self.children[0].children[0]), ('.recur', self.children[1]), ('attrset', self.children[0].attr), 'update']
        elif isinstance(self.children[0], Variable):
            return [('.recur', self.children[1]), ('.setvar', self.children[0])]

class DropExpr(Node):
    def __init__(self, data):
        self.children = [(AssignExpr, data)]
    def compile(self):
        ans = self.children[0].compile()
        ans.append('pop')
        return ans

class Literal(Expression):
    def __init__(self, value):
        self.value = value
        self.children = []
    def compile(self):
        return [('pushc', self.value)]

class Variable(Expression):
    def __init__(self, name):
        self.name = name
        self.children = []
    def compile(self):
        return [('.getvar', self)]

class CommaExpr(Expression):
    def __init__(self, data):
        if len(data.value) == 0: self.handle_no_args(data)
        data = data.value
        self.children = []
        idx0 = 0
        idx = 0
        while idx <= len(data):
            if idx == len(data) or (isinstance(data[idx], lexer.Operator) and data[idx].value == ','):
                if idx0 != len(data): self.handle(data[idx0:idx])
                idx0 = idx + 1
            idx += 1
    def handle_no_args(self, data):
        pass
    def handle(self, chk):
        self.children.append((AssignExpr, chk))
    def compile(self):
        ans = []
        for i in self.children:
            ans.append(('.recur', i))
        return ans

class ArrayExpr(CommaExpr):
    def compile(self):
        ans = super().compile()
        ans.append(('makearr', len(self.children)))
        return ans

class ObjectExpr(CommaExpr):
    def __init__(self, data):
        self.keys = []
        super().__init__(data)
    def handle(self, chk):
        if not chk:
            raise lexer.VKSyntaxError(None, -1, -1, 'empty expression')
        elif len(chk) <= 2 or not isinstance(chk[1], lexer.Operator) or chk[1].value != ':':
            raise lexer.VKSyntaxError.fromLexem(chk[min(len(chk)-1, 1)], 'invalid object declaration')
        elif not isinstance(chk[0], (lexer.Identifier, lexer.StringLiteral)):
            raise lexer.VKSyntaxError.fromLexem(chk[0], 'invalid property name')
        else:
            self.keys.append(chk[0].value)
            self.children.append((AssignExpr, chk[2:]))
    def compile(self):
        ans = super().compile()
        ans.append(('makeobj', self.keys))
        return ans

class CallExpr(CommaExpr):
    def __init__(self, name, args):
        self.name = name
        super().__init__(args)

class SingleArgCallExpr(CallExpr):
    def __init__(self, name, args):
        self.cntr = 0
        super().__init__(self, name, args)
    def handle(self, chk):
        self.cntr += 1
        if self.cntr == 2 and chk:
            raise lexer.VKSyntaxError.fromLexem(chk[0], 'too many arguments for built-in or API call')
        return super().handle(chk)
    def compile(self):
        ans = super().compile()
        if not ans:
            ans.append(self.default())
        ans.append(self.emit_call())
        return ans

class APICallExpr(SingleArgCallExpr):
    def default(self): return ('makeobj', 0)
    def emit_call(self): return ('apicall', self.name)

class BuiltinCallExpr(SingleArgCallExpr):
    def handle_no_args(self, data):
        raise lexer.VKSyntaxError.fromLexem(data, 'built-in function takes exactly one argument')
    def emit_call(self): return ('unaryop', self.name)

class MethodCallExpr(CallExpr):
    def __init__(self, obj, name, args):
        super().__init__(name, args)
        self.children.insert(0, (AtomicExpr, obj))
    def compile(self):
        ans = super().compile()
        ans.append(('methodcall', self.name, len(ans) - 1))
        ans.append('update')
        return ans

class ArrayGetExpr(Expression):
    def __init__(self, arr, idx):
        self.children = [(AtomicExpr, arr), (AssignExpr, idx)]
    def compile(self):
        return [('.recur', self.children[0]), ('.recur', self.children[1]), 'arrayget']

class AttrGetExpr(Expression):
    def __init__(self, arr, attr):
        self.children = [(AtomicExpr, arr)]
        self.attr = attr
    def compile(self):
        return [('.recur', self.children[0]), ('attrget', self.attr)]

class FilterExpr(Expression):
    def __init__(self, arr, attr):
        self.children = [(AssignExpr, arr)]
        self.attr = attr
    def compile(self):
        return [('.recur', self.children[0]), ('attrfilter', self.attr)]

def parse(code):
    if isinstance(code, str):
        code = lexer.lex(code)
    root = CodeBlock(code)
    assert not hasattr(root, 'replace')
    stack = [[root.children, 0]]
    while stack:
        x = stack[-1]
        l, i = x
        if i == len(l):
            stack.pop()
            continue
        x[1] += 1
        while True:
            if isinstance(l[i], tuple):
                cls = l[i][0]
                if not isinstance(cls, type): cls = type(cls)
#               print(l[i-1:i+1], cls, l[i][1:])
                l[i] = cls(*l[i][1:])
            elif hasattr(l[i], 'replace'):
                l[i] = l[i].replace
            elif hasattr(l[i], 'children'):
                stack.append([l[i].children, 0])
                break
            else: break
    return root
