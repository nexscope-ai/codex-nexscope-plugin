"""Remove unapproved supplier mentions from prose without changing API contracts.

This is a partial cleanup. Protected routes, identifiers, code examples and Git
history still need a separate compatibility migration and release review.
"""
import re

PROVIDERS = re.compile(
    r"(?<![A-Za-z0-9])(?:seller[\s_-]*sprite|jungle[\s_-]*scout|"
    r"chuhaijiang|geek[\s_-]*bi|zhihuiya|patsnap|sorftime|jiimore|sif|"
    r"keepa|seerfar|mpstats|echotik|wally[\s_-]*smarter|data[\s_-]*for[\s_-]*seo|"
    r"\u51fa\u6d77\u5320|\u667a\u6167\u82bd)(?![A-Za-z0-9])", re.I
)
PROTECTED = re.compile(
    r"```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\r\n]+`|"
    r"https?://[^\s<>\"]+|(?m:^name:[^\r\n]*)|"
    r"(?m:^version:[^\r\n]*)|(?m:^\s*[^\r\n]*LICENSE[^\r\n]*$)|"
    r"(?:\.?\.?/)[A-Za-z0-9_][^\s<>\"]*"
)

def clean(text: str) -> str:
    tokens = []
    def protect(match):
        tokens.append(match.group())
        return f"\ue000{len(tokens)-1}\ue001"
    safe = PROTECTED.sub(protect, text)
    safe = PROVIDERS.sub("Nexscope", safe)
    safe = re.sub(r"Nexscope\s+(?:and|through|via|by)\s+Nexscope", "Nexscope", safe)
    safe = re.sub(r"Nexscope[ ]+Nexscope", "Nexscope", safe)
    return re.sub(r"\ue000(\d+)\ue001", lambda m: tokens[int(m[1])], safe)
