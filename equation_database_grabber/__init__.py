import sympy
from PIL import Image
from pix2tex.cli import LatexOCR
from IPython.display import display, Math, Latex
from latex2sympy2 import latex2sympy, latex2latex

def img2tex(img_path):
    img = Image.open(img_path)
    model = LatexOCR()
    tex = model(img)
    return tex

def tex2sym(tex, clean_tex):
    if clean_tex:
        clean = tex.replace(r"\bigl(","("
                  ).replace(r"\bigr)",")"
                  ).replace(r"\left(","("
                  ).replace(r"\right)",")"
                  ).replace(r'\ ',''
                  ).replace('=','')
    else:
        clean = tex

    #try:
    sym = latex2sympy(clean)
    return sym
    #except Exception as e:
    #    sym = None
    #    # show full exception
    #    print(e)

def grab(img_path, print_tex = False, clean_tex = True, equation_database = True,cpp = True, fortran = True, mathematica= True, python=True):
    print("original image:")
    img = Image.open(img_path)
    display(img)
    print("IMG -> TEX:")
    tex = img2tex(img_path)
    display(Math(tex))
    if print_tex:
        print(tex)

    print("TEX -> SYM:")
    sym = None
    try:
        sym = tex2sym(tex, clean_tex)
        display(sym)
    except Exception as e:
        print("No sympy representation found")
        # show full exception
        print(e)

    cpp_code = None
    mathematica_code = None
    python_code = None
    fortran_code = None
    edb_code = None

    if cpp:
        print("\nSYM -> CPP:")
        try:
            cpp_code = sympy.ccode(sym)
            print(cpp_code)
        except Exception as e:
            print("No cpp representation found")
            # show full exception
            print(e)
    if mathematica:
        print("\nSYM -> Mathematica:")
        try:
            mathematica_code = sympy.mathematica_code(sym)
            print(mathematica_code)
        except Exception as e:
            print("No mathematica representation found")
            # show full exception
            print(e)
    if python:
        print("\nSYM -> Python:")
        try:
            python_code = sympy.pycode(sym)
            print(python_code)
        except Exception as e:
            print("No python representation found")
            # show full exception
            print(e)
    if fortran:
        print("\nSYM -> Fortran:")
        try:
            fortran_code = sympy.fcode(sym)
            print(fortran_code)
        except Exception as e:
            print("No fortran representation found")
            # show full exception
            print(e)
    if equation_database:
        print("\nSYM -> EDB:")
        try:
            edb_code = sympy.python(sym)
            print(edb_code)
        except Exception as e:
            print("No ebd representation found")
            # show full exception
            print(e)


    return sym, tex, cpp_code, mathematica_code, python_code, fortran_code, edb_code