"""ELT v1: lexer -> recursive descent parser -> semantic analysis -> MySQL 8."""
from dataclasses import dataclass, asdict
from decimal import Decimal
import json
import re

VERSION = "1.0.0"
MAX_BYTES = 65536

class CompileError(ValueError):
    def __init__(self, stage, message, line=1, column=1):
        self.diagnostic = dict(stage=stage, message=message, line=line, column=column)
        super().__init__(f"{stage}: linha {line}, coluna {column}: {message}")

@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int

PATTERN = re.compile(
    r'(?P<SPACE>\s+)|(?P<COMMENT>\#[^\n]*)|'
    r'(?P<STRING>"(?:[^"\\\n]|\\["\\/bfnrt]|\\u[0-9a-fA-F]{4})*")|'
    r'(?P<NUMBER>\d+(?:\.\d+)?)|(?P<OP>>=|<=|==|>|<)|'
    r'(?P<WORD>[A-Z_]+)'
)

def tokenize(source):
    if len(source.encode("utf-8")) > MAX_BYTES:
        raise CompileError("lexico", "Arquivo excede 64 KiB.")
    result, pos, line, col = [], 0, 1, 1
    while pos < len(source):
        match = PATTERN.match(source, pos)
        if not match:
            raise CompileError("lexico", f"Caractere inesperado: {source[pos]!r}", line, col)
        value, kind = match.group(), match.lastgroup
        if kind not in ("SPACE", "COMMENT"):
            result.append(Token(kind, value, line, col))
        lines = value.split("\n")
        line += len(lines) - 1
        col = col + len(value) if len(lines) == 1 else len(lines[-1]) + 1
        pos = match.end()
    result.append(Token("EOF", "", line, col))
    return result

@dataclass(frozen=True)
class Rule:
    name: str
    cabin: str
    phase: str
    metric: str
    operator: str
    threshold: str
    unit: str
    duration: str
    gap: str
    severity: str
    line: int
    column: int

class Parser:
    def __init__(self, tokens):
        self.tokens, self.i = tokens, 0

    def take(self, kind, value=None):
        token = self.tokens[self.i]
        if token.kind != kind or (value is not None and token.value != value):
            expected = value or kind
            raise CompileError("sintatico", f"Esperado {expected}; encontrado {token.value or 'fim do arquivo'}.",
                               token.line, token.column)
        self.i += 1
        return token

    def word(self, value):
        return self.take("WORD", value)

    def parse(self):
        rules = []
        while self.tokens[self.i].kind != "EOF":
            start = self.word("REGRA")
            name = json.loads(self.take("STRING").value)
            self.word("CABINE")
            cabin = json.loads(self.take("STRING").value)
            self.word("FASE")
            phase = self.take("WORD").value
            self.word("QUANDO")
            metric = self.take("WORD").value
            op = self.take("OP").value
            threshold = self.take("NUMBER").value
            unit = self.take("WORD").value
            self.word("DURANTE")
            duration = self.take("NUMBER").value
            self.word("SEGUNDOS")
            self.word("LACUNA_MAXIMA")
            gap = self.take("NUMBER").value
            self.word("SEGUNDOS")
            self.word("CLASSIFICAR")
            severity = self.take("WORD").value
            self.word("FIM")
            rules.append(Rule(name, cabin, phase, metric, op, threshold, unit,
                              duration, gap, severity, start.line, start.column))
        if not rules:
            raise CompileError("sintatico", "Escreva pelo menos uma REGRA.")
        return rules

def validate(rules, cabins):
    known, names = set(cabins), set()
    if not known or any(not re.fullmatch(r"cabine-\d{3,}", c) for c in known):
        raise CompileError("semantico", "Cadastro de cabines inválido.")
    if len(rules) > 100:
        raise CompileError("semantico", "Limite de 100 regras por arquivo.")
    for r in rules:
        def fail(message):
            raise CompileError("semantico", message, r.line, r.column)
        if not r.name.strip() or len(r.name) > 100 or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in r.name):
            fail("Nome deve conter 1 a 100 caracteres imprimíveis.")
        if r.name in names:
            fail("Nome de regra duplicado.")
        names.add(r.name)
        if r.cabin not in known:
            fail("Cabine não cadastrada.")
        if r.phase not in ("A", "B", "C", "QUALQUER"):
            fail("FASE deve ser A, B, C ou QUALQUER.")
        units = {"TEMPERATURA": "C", "CORRENTE": "A"}
        if r.metric not in units:
            fail("Grandeza deve ser TEMPERATURA ou CORRENTE.")
        if r.unit != units[r.metric]:
            fail(f"{r.metric} exige unidade {units[r.metric]}.")
        if not Decimal(0) <= Decimal(r.threshold) < Decimal(10)**7:
            fail("Limite fora do domínio da tabela de leituras.")
        if not Decimal(r.duration) == int(Decimal(r.duration)) or not 0 <= Decimal(r.duration) <= 86400:
            fail("Duração deve ser um inteiro entre 0 e 86400 segundos.")
        if not Decimal(r.gap) == int(Decimal(r.gap)) or not 1 <= Decimal(r.gap) <= 3600:
            fail("Lacuna deve ser um inteiro entre 1 e 3600 segundos.")
        if r.severity not in ("ATENCAO", "MODERADO", "CRITICO"):
            fail("Classificação deve ser ATENCAO, MODERADO ou CRITICO.")

def generate_sql(r):
    """Read-only query; caller binds start/end UTC datetimes. No user SQL accepted."""
    phases = "ABC" if r.phase == "QUALQUER" else r.phase
    op = "=" if r.operator == "==" else r.operator
    threshold = str(Decimal(r.threshold))
    duration, gap = int(Decimal(r.duration)), int(Decimal(r.gap))
    metric = {"TEMPERATURA": "temperatura", "CORRENTE": "corrente"}[r.metric]
    name = r.name.encode("utf-8").hex()
    branches = []
    for p in phases:
        c = p.lower()
        branches.append(f"""SELECT coletado_em, '{p}' AS fase,
          CASE WHEN qualidade_{c} = 'ok' AND fase_{c} {op} {threshold}
               THEN 1 ELSE 0 END AS hit
          FROM raw""")
    phase_sql = "\nUNION ALL\n".join(branches)
    return f"""WITH raw AS (
 SELECT * FROM leituras
 WHERE cabine_id = '{r.cabin}' AND tipo = '{metric}'
 AND coletado_em >= %(start)s AND coletado_em < %(end)s
), phases AS (
 {phase_sql}
), samples AS (
 SELECT coletado_em, fase, MIN(hit) AS hit
 FROM phases GROUP BY coletado_em, fase
), previous AS (
 SELECT *, LAG(coletado_em) OVER w AS prev_time, LAG(hit) OVER w AS prev_hit
 FROM samples WINDOW w AS (PARTITION BY fase ORDER BY coletado_em)
), boundaries AS (
 SELECT *, CASE WHEN hit = 1 AND (
 COALESCE(prev_hit, 0) = 0 OR
 TIMESTAMPDIFF(MICROSECOND, prev_time, coletado_em) > {gap} * 1000000
 ) THEN 1 ELSE 0 END AS new_group FROM previous
), grouped AS (
 SELECT *, SUM(new_group) OVER (
 PARTITION BY fase ORDER BY coletado_em ROWS UNBOUNDED PRECEDING) AS grp
 FROM boundaries
), runs AS (
 SELECT *, MIN(CASE WHEN hit = 1 THEN coletado_em END)
 OVER (PARTITION BY fase, grp) AS started FROM grouped
)
SELECT CONVERT(X'{name}' USING utf8mb4) AS regra,
 '{r.cabin}' AS cabine, '{metric}' AS grandeza, fase,
 '{r.severity}' AS severidade, MIN(coletado_em) AS inicio,
 MIN(CASE WHEN TIMESTAMPDIFF(MICROSECOND, started, coletado_em) >= {duration} * 1000000
 THEN coletado_em END) AS confirmado_em,
 MAX(coletado_em) AS ultima_leitura,
 TIMESTAMPDIFF(MICROSECOND, MIN(coletado_em), MAX(coletado_em))/1000000 AS duracao_observada_s
FROM runs WHERE hit = 1 GROUP BY fase, grp
HAVING confirmado_em IS NOT NULL
ORDER BY inicio, fase"""

def compile_source(source, cabins):
    tokens = tokenize(source)
    rules = Parser(tokens).parse()
    validate(rules, cabins)
    return {
        "compiler_version": VERSION,
        "tokens": [asdict(t) for t in tokens],
        "ast": [asdict(r) for r in rules],
        "queries": [{"name": r.name, "sql": generate_sql(r)} for r in rules]
    }
