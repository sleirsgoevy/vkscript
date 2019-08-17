import json, collections

class Lexem:
    def __init__(self, code, line, startpos, value):
        self.code = code
        self.line = line
        self.startpos = startpos
        self.value = value
    @classmethod
    def read(self, rd):
        code, line, startpos = rd.source, rd.line, rd.pos
        try: data = self._read(rd)
        except VKSyntaxError as e:
            if e.code == None:
                e.code, e.line, e.startpos = code, line, startpos
            raise e
        return self(code, line, startpos, data)
    @classmethod
    def fromLexem(self, l, s):
        return self(l.code, l.line, l.startpos, s)
    def __repr__(self):
        return '%s(%d, %d, %r)'%(repr(type(self))[8:-2], self.line, self.startpos, self.value)

class VKSyntaxError(Lexem, Exception):
    def __str__(self):
        if self.code == None: return self.value
        return self.value+'\n'+' '*29+self.code.split('\n')[self.line-1]+'\n'+' '*(self.startpos+28)+'^'

class Identifier(Lexem):
    @classmethod
    def _read(self, rd):
        ans = ''
        while True:
            c = rd.get()
            if not (c.isalnum() or c == '_'): break
            ans += c
        rd.unget()
        return ans

class Operator(Lexem):
    OPS = ['+', '-', '*', '/', '%', '==', '!=', '>', '<', '>=', '<=', '||', '&&', '!', ',', ';', '.', '@.', '=', '&', '|', '>>', '<<', '~', ':', '/*', '//']
    ops_trie = {}
    for i in OPS:
        cur = ops_trie
        for j in i:
            if j not in cur: cur[j] = {}
            cur = cur[j]
    del i, j, cur
    @classmethod
    def _read(self, rd):
        ans = ''
        cur = self.ops_trie
        while True:
            c = rd.get()
            if c not in cur: break
            ans += c
            cur = cur[c]
        rd.unget()
        if ans not in self.OPS:
            if c.isalnum() or c == '_' or c == ' ': c = ''
            raise VKSyntaxError(None, -1, -1, 'unknown operator: '+ans+c)
        return ans

class StringLiteral(Lexem):
    @classmethod
    def _read(self, rd):
        ans = ''
        c = rd.get()
        prev = None
        while True:
            c2 = rd.rawget()
            if c2 == None or c2 == '\n':
                rd.unget()
                raise VKSyntaxError(rd.source, rd.line, rd.pos, 'unexpected EOL while parsing')
            if c == "'" and c2 == '"' and prev != '\\': ans += '\\'
            if c2 == c and prev != '\\': break
            ans += c2
            prev = c2
        try: return json.loads('"'+ans+'"')
        except json.JSONDecodeError: raise VKSyntaxError(None, -1, -1, 'invalid string literal: '+ans)

class Enclosed(Lexem):
    def __iter__(self): return iter(self.value)
    @classmethod
    def _read(self, rd): return []

class EnclosedParens(Enclosed): ENDING = ')'
class EnclosedSquare(Enclosed): ENDING = ']'
class EnclosedCurly(Enclosed): ENDING = '}'
class EnclosedTernary(Enclosed): ENDING = ':'
class Source(Enclosed): ENDING = None

Enclosed.KINDS = {'(': EnclosedParens, '[': EnclosedSquare, '{': EnclosedCurly, '?': EnclosedTernary}

class SourceReader:
    def __init__(self, source):
        self.line = 1
        self.pos = 1
        self.prev = (0, 1, 1)
        self.source = source
        self.spos = 0
    def rawget(self):
        self.prev = (self.spos, self.line, self.pos)
        if self.spos == len(self.source):
            return None
        ch = self.source[self.spos]
        self.spos += 1
        if ch == '\n':
            self.line += 1
            self.pos = 1
        else:
            self.pos += 1
        return ch
    def unget(self):
        self.spos, self.line, self.pos = self.prev
    def get(self):
        ch = self.rawget()
        if ch == None: return None
        if ch.isspace():
            while ch != None and ch.isspace(): ch = self.rawget()
            self.unget()
            return ' '
        return ch

def lex(src):
    rd = SourceReader(src)
    stack = [Source(src, 1, 1, [])]
    while True:
        c = rd.get()
        rd.unget()
        if c == None: break
        elif c == ' ': continue
        elif c.isalnum() or c == '_':
            stack[-1].value.append(Identifier.read(rd))
        elif c in '"'"'":
            stack[-1].value.append(StringLiteral.read(rd))
        elif c in Enclosed.KINDS:
            i = Enclosed.KINDS[c].read(rd)
            stack[-1].value.append(i)
            stack.append(i)
            rd.get()
        elif c == stack[-1].ENDING:
            stack.pop()
            rd.get()
        elif c in (')', ']', '}'):
            raise VKSyntaxError(rd.source, rd.line, rd.pos, 'non-matching bracket')
        else:
            op = Operator.read(rd)
            if op.value == '//':
                while rd.rawget() != '\n': pass
            elif op.value == '/*':
                while True:
                    while rd.rawget() != '*': pass
                    if rd.rawget() == '/': break
                    rd.unget()
            else:
                stack[-1].value.append(op)
    if len(stack) != 1:
        raise VKSyntaxError(rd.source, rd.line, rd.pos, 'unexpected EOF while parsing')
    return stack[0]
