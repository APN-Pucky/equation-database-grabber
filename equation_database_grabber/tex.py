import os
import re
import subprocess
import tarfile
import tempfile


def inject_labels(tex_source):
    env_pattern = re.compile(
        r"\\begin\{(equation|align|gather)\}(.*?)\\end\{\1\}", re.DOTALL
    )

    contents = []

    def replacer(match, counter=[0]):
        env = match.group(1)
        content = match.group(2)
        counter[0] += 1
        label = f"eq:auto-{counter[0]}"
        contents.append((label, content))
        return f"\\begin{{{env}}}{content}\n\\label{{{label}}}\\end{{{env}}}"

    return env_pattern.sub(replacer, tex_source), contents


def extract_equation_numbers_from_aux(aux_path):
    """
    Extracts label-to-equation-number mappings from a LaTeX .aux file.

    Returns:
        A dictionary mapping label names to their equation numbers (as strings).
    """
    label_pattern = re.compile(r"\\newlabel\{([^}]+)\}\{\{([^}]+)\}\{[^}]*\}")
    equation_labels = {}

    with open(aux_path, "r", encoding="utf-8") as aux_file:
        for line in aux_file:
            match = label_pattern.search(line)
            if match:
                label = match.group(1)
                number = match.group(2)
                equation_labels[label] = number

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

        # Now run latexmk/pdflatex to generate the .aux file
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_file_path],
            cwd=temp_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"Warning: pdflatex failed with return code {result.returncode}")
            print(f"stderr: {result.stderr}")
            # Continue anyway as .aux file might still be generated

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
