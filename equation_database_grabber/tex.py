import warnings

from latex2sympy2 import latex2latex, latex2sympy


def tex2sym(tex, clean_tex, log_is_ln=False):
    if clean_tex:
        clean = (
            tex.replace(r"\bigl(", "(")
            .replace(r"\bigr)", ")")
            .replace(r"\left(", "(")
            .replace(r"\right)", ")")
            .replace(r"\ ", "")
            # .replace("=", "")
        )
    else:
        clean = tex

    if log_is_ln:
        clean = clean.replace(r"\log", r"\ln")

    if r"\log" in clean:
        warnings.warn(
            "logarithm 'log' is log10 in sympy, use log_is_ln = True to convert to ln"
        )

    # try:
    sym = latex2sympy(clean)
    return sym
    # except Exception as e:
    #    sym = None
    #    # show full exception
    #    print(e)
