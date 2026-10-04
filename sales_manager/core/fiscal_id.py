"""Spanish tax identification numbers (NIF of people, NIE of foreigners, CIF of companies): check digit validation,
so a mistyped number is caught before it is printed on every invoice."""

import re

DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
CIF_LETTERS = "JABCDEFGHI"


def normalize(value: str) -> str:
    return re.sub(r"[\s.-]", "", str(value or "")).upper()


def tax_id_problem(value: str) -> str | None:
    """None when the number is a valid Spanish NIF, NIE or CIF; otherwise what is wrong with it, in plain words."""
    v = normalize(value)
    if not v:
        return "Falta el NIF."
    if re.fullmatch(r"\d{8}[A-Z]", v):
        return None if DNI_LETTERS[int(v[:8]) % 23] == v[8] else "La letra del NIF no corresponde a sus números."
    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", v):
        number = int(str("XYZ".index(v[0])) + v[1:8])
        return None if DNI_LETTERS[number % 23] == v[8] else "La letra del NIE no corresponde a sus números."
    if re.fullmatch(r"[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]", v):
        digits = v[1:8]
        total = sum(int(d) for d in digits[1::2])
        total += sum(sum(divmod(int(d) * 2, 10)) for d in digits[0::2])
        check = (10 - total % 10) % 10
        if v[0] in "PQRSWN":
            expected = {CIF_LETTERS[check]}
        elif v[0] in "ABEH":
            expected = {str(check)}
        else:
            expected = {str(check), CIF_LETTERS[check]}
        return None if v[8] in expected else "El dígito de control del CIF no es correcto."
    return "No parece un NIF, NIE o CIF español (8 números y letra, o letra, 7 números y control)."
