
"""
PromptOps CLI - Main entry point
"""
import typer
from typing import Optional
from pathlib import Path

app = typer.Typer(
    name="promptops",
    help="Git-style version control for LLM prompts",
    add_completion=False,
)


@app.command()
def init(
    path: Optional[Path] = typer.Argument(
        None,
        help="Directory to initialize (default: current directory)"
    )
):
    """
    Initialize a new PromptOps project
    
    Creates a .promptops directory with configuration files
    """
    from promptops.cli.commands import init_command
    init_command(path)


@app.command()
def add(
    files: list[str] = typer.Argument(..., help="Prompt files to stage"),
):
    """
    Stage prompt files for commit
    
    Example:
        promptops add my_prompt.yaml
        promptops add prompts/*.yaml
    """
    from promptops.cli.commands import add_command
    add_command(files)


@app.command()
def commit(
    message: str = typer.Option(..., "-m", "--message", help="Commit message"),
    author: Optional[str] = typer.Option(None, "--author", help="Commit author"),
):
    """
    Commit staged prompts
    
    Example:
        promptops commit -m "Initial prompt version"
        promptops commit -m "Fix hallucination" --author "Jane Doe"
    """
    from promptops.cli.commands import commit_command
    commit_command(message, author)


@app.command()
def log(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of commits to show"),
    oneline: bool = typer.Option(False, "--oneline", help="Show compact one-line format"),
):
    """
    Show commit history
    
    Example:
        promptops log
        promptops log --limit 5
        promptops log --oneline
    """
    from promptops.cli.commands import log_command
    log_command(limit, oneline)


@app.command()
def diff(
    version_a: str = typer.Argument(..., help="First version (hash or HEAD~N)"),
    version_b: Optional[str] = typer.Argument(None, help="Second version (default: HEAD)"),
):
    """
    Show differences between two prompt versions
    
    Example:
        promptops diff abc123
        promptops diff HEAD~1 HEAD
        promptops diff abc123 def456
    """
    from promptops.cli.commands import diff_command
    diff_command(version_a, version_b)


@app.command()
def status():
    """
    Show working directory status
    
    Displays staged and unstaged files
    """
    from promptops.cli.commands import status_command
    status_command()


@app.command()
def rollback(
    steps: int = typer.Option(1, "--steps", "-n", help="Number of versions to rollback"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """
    Rollback to a previous version
    
    Example:
        promptops rollback
        promptops rollback --steps 3
        promptops rollback --force
    """
    from promptops.cli.commands import rollback_command
    rollback_command(steps, force)

@app.command()
def eval(
    run: bool = typer.Option(False, "--run", help="Run evaluation on current HEAD"),
    version: Optional[str] = typer.Option(None, "--version", help="Specific version hash to evaluate"),
    compare: bool = typer.Option(False, "--compare", help="Compare with parent version"),
    samples: int = typer.Option(10, "--samples", "-n", help="Number of test samples"),
):
    """
    Run evaluation pipeline on a prompt version
    
    Example:
        promptops eval --run
        promptops eval --version abc123 --samples 20
        promptops eval --run --compare
    """
    from promptops.cli.commands import eval_command
    eval_command(run, version, compare, samples)


@app.command()
def version():
    """Show PromptOps version"""
    typer.echo("PromptOps v0.1.0")



def main():
    """Entry point for the CLI"""
    app()


if __name__ == "__main__":
    main()