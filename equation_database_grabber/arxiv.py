import os
import re
import subprocess
import tarfile
import tempfile

import requests
import sympy

from equation_database_grabber.tex import tex2sym


def clean(s):
    s = s.replace(r"\begin{aligned}", "").replace(r"\end{aligned}", "")
    s = s.strip()
    s = re.sub(r"\\,[,\.]$", "", s)
    return s.strip()


def inject_labels(tex_source):
    env_pattern = re.compile(
        r"\\begin\{(equation|align|gather)\}(.*?)\\end\{\1\}", re.DOTALL
    )

    contents = []

    def replacer(match, counter=[0]):
        env = match.group(1)
        content = match.group(2)

        if env == "align":
            # Handle align environment with multiple lines
            # Split by \\ but be careful not to split escaped backslashes
            lines = re.split(r"(?<!\\)\\\\(?!\\)", content)

            modified_lines = []
            for i, line in enumerate(lines):
                line = line.strip()
                if line and not re.search(r"\\nonumber", line):
                    counter[0] += 1
                    label = f"eq:auto-{counter[0]}"
                    # Remove any existing \label{} commands from the line
                    line = re.sub(r"\\label\{[^}]*\}", "", line)
                    contents.append((label, clean(line)))
                    # Add label to the line
                    line = f"{line} \\label{{{label}}}"
                modified_lines.append(line)

            # Rejoin the lines with \\
            modified_content = " \\\\\n".join(modified_lines)
            return f"\\begin{{{env}}}{modified_content}\\end{{{env}}}"
        else:

            counter[0] += 1
            label = f"eq:auto-{counter[0]}"
            # Remove any existing \label{} commands from the content
            content = re.sub(r"\\label\{[^}]*\}", "", content)
            contents.append((label, clean(content)))
            return f"\\begin{{{env}}}{content}\\label{{{label}}}\\end{{{env}}}"

    # Strip begin/end of aligned and split environments

    return env_pattern.sub(replacer, tex_source), contents


def extract_equation_numbers_from_aux(aux_path):
    """
    Extracts label-to-equation-number mappings from a LaTeX .aux file.

    Returns:
        A dictionary mapping label names to their equation numbers (as strings).
    """
    label_pattern = re.compile(
        r"\\newlabel\{([^}]+)\}\{\{[^}]+\}\{[^}]*\}\{[^}]*\}\{([^}]+)\}\{[^}]*\}\}"
    )
    equation_labels = {}

    with open(aux_path, "r", encoding="utf-8") as aux_file:
        for line in aux_file:
            match = label_pattern.search(line)
            if match:
                label = match.group(1)
                number = match.group(2).replace("equation.", "")
                equation_labels[label] = number
    logging.debug(f"Extracted equation labels: {equation_labels}")
    return equation_labels


def get_equations(arxiv_tar_gz):
    """
    Extracts equations from a LaTeX source file in an arXiv tar.gz archive.

    Args:
        arxiv_tar_gz: Path to the arXiv tar.gz file.
    """
    # Validate input file exists
    if not os.path.exists(arxiv_tar_gz):
        raise FileNotFoundError(f"Archive file not found: {arxiv_tar_gz}")

    # First extract the tar.gz file into a temporary directory

    with tempfile.TemporaryDirectory() as temp_dir:
        with tarfile.open(arxiv_tar_gz, "r:gz") as tar:
            tar.extractall(path=temp_dir)

        # Find the .tex file in the extracted contents
        tex_files = [f for f in os.listdir(temp_dir) if f.endswith(".tex")]
        if not tex_files:
            raise FileNotFoundError("No .tex file found in the archive.")

        # Use the first .tex file (could be made more sophisticated)
        if len(tex_files) > 1:
            print(f"Warning: Multiple .tex files found. Using: {tex_files[0]}")

        tex_file_path = os.path.join(temp_dir, tex_files[0])

        # Read the .tex file and inject labels
        with open(tex_file_path, "r", encoding="utf-8") as tex_file:
            tex_content = tex_file.read()

        labeled_tex, contents = inject_labels(tex_content)

        # Write the modified content back to a new file
        with open(tex_file_path, "w", encoding="utf-8") as labeled_file:
            labeled_file.write(labeled_tex)

        # Now run latexmk to generate the .aux file
        result = subprocess.run(
            ["latexmk", "-pdflatex", "-interaction=nonstopmode", tex_file_path],
            cwd=temp_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"Warning: pdflatex failed with return code {result.returncode}")
            print(f"stderr: {result.stderr}")
            # Continue anyway as .aux file might still be generated
            print("Path to .tex file:", tex_file_path)

        # replace tex suffix with aux
        aux_file_path = os.path.splitext(tex_file_path)[0] + ".aux"
        if not os.path.exists(aux_file_path):
            raise FileNotFoundError(
                "No .aux file generated. Ensure pdflatex ran successfully."
            )

        # Extract equation numbers from the .aux file
        equation_labels = extract_equation_numbers_from_aux(aux_file_path)

        # replace label first member in contents with the equation number
        # then return it as a dictionary
        ret = {}
        for label, content in contents:
            if label in equation_labels:
                ret[equation_labels[label]] = content
            else:
                raise ValueError(f"Label {label} not found in .aux file.")

        return ret


def get_bibtex(arxiv_identifier):
    """
    Fetches the BibTeX entry for a given arXiv identifier from inspirehep.net.
    """
    url = f"https://inspirehep.net/api/arxiv/{arxiv_identifier}?format=bibtex"
    response = requests.get(url)
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch BibTeX of {arxiv_identifier} via {url}: {response.text}"
        )
    return response.text.strip()


def generate_equation_database_entry(
    arxiv_identifier, arxiv_source_tar_gz, output_dir=None, exist_ok=True
):
    """
    Generates an equation database entry for a given arXiv identifier and source tar.gz file.

    Args:
        arxiv_identifier: The arXiv identifier (e.g., '2506.23162v1').
        arxiv_source_tar_gz: Path to the tar.gz file containing the LaTeX source.

    Returns:
        A dictionary with the BibTeX entry and equations extracted from the source.
    """
    bibtex = get_bibtex(arxiv_identifier)
    equations = get_equations(arxiv_source_tar_gz)

    if not output_dir:
        output_dir = os.getcwd()

    # create folder f"arxiv_{arxiv_identifier.replace('.', '_')}" in output_dir
    output_folder = os.path.join(
        output_dir, f"arxiv_{arxiv_identifier.replace('.', '_')}"
    )
    os.makedirs(output_folder, exist_ok=exist_ok)

    # create empty __init__.py in output_folder
    init_file_path = os.path.join(output_folder, "__init__.py")
    with open(init_file_path, "w") as init_file:
        init_file.write("import sympy\n")
        init_file.write("from equation_database.util.doc import bib, equation\n\n")

        init_file.write("@bib()\n")
        init_file.write("def bibtex():\n")
        init_file.write('    bibtex: str = r"""\n')
        init_file.write(bibtex)
        init_file.write('"""\n')
        init_file.write("    return bibtex\n")

        for eq_num, eq_content in sorted(
            equations.items(),
            key=lambda x: [
                int(part) if part.isdigit() else part
                for part in re.split(r"(\d+)", x[0])
            ],
        ):
            clean_eq_content = (
                eq_content.replace("\n", "")
                .replace("&", "")
                .replace("\\dd", "\\,\\mathrm{d}")
                .strip()
            )

            failed = False
            sym = None
            try:
                sym = tex2sym(
                    clean_eq_content.replace("\\\\", ""), True, log_is_ln=False
                )
                print(sym)
            except Exception as e:
                print(f"Failed to convert equation {eq_num} to sympy: {e}")
                failed = True

            try:
                edb_code = sympy.python(sym)
                print(edb_code)
                # split lines: first lines are parameters, last line is the equation
                edb_code_lines = edb_code.splitlines()
                if len(edb_code_lines) < 1:
                    print(
                        f"Equation {eq_num} does not have enough lines for parameters and equation."
                    )
                    failed = True
                else:
                    equation = edb_code_lines[-1]
                    parameters = edb_code_lines[:-1]
                    # append comma to parameters
                    parameters = [
                        f'    {param.replace("Symbol","sympy.Symbol")},\n'
                        for param in parameters
                    ]
                    equation = f"    return {equation}"
            except Exception as e:
                print(f"Failed to convert equation {eq_num} to Python: {e}")
                failed = True

            if failed:
                parameters = []
                equation = (
                    f'    raise NotImplementedError("Automatic conversion failed")\n'
                )

            # remove trailing \\,, or \\,.
            clean_eq_content = re.sub(r"\\,[,\.]$", "", clean_eq_content)
            clean_eq_content = re.sub(r"_(\\text{[^}]+})", r"_\{\1\}", clean_eq_content)
            clean_eq_content = re.sub(r"_(\\[a-zA-Z]+})", r"_\{\1\}", clean_eq_content)
            clean_eq_content = clean_eq_content.replace(r"_-", "_{-}")
            clean_eq_content = clean_eq_content.strip()

            # check if sym is a sympy expression and not a Equation
            if isinstance(sym, sympy.Basic) and not isinstance(sym, sympy.Eq):
                equation = re.sub("^    return e =", "    return ", equation)

            init_file.write(f"\n\n")
            init_file.write(f"@equation(\n")
            init_file.write(f'    latex=r"{clean_eq_content}"\n')
            init_file.write(f")\n")
            init_file.write(f'def equation_{eq_num.replace(".", "_")}(\n')
            for param in parameters:
                init_file.write(f"{param}")
            init_file.write(f"):\n")
            init_file.write(f"{equation}")
