"""
CLI command implementations
"""
import os
import json
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich import box

console = Console()


def init_command(path: Optional[Path] = None):
    """
    Initialize a new PromptOps project
    """
    project_root = path or Path.cwd()
    promptops_dir = project_root / ".promptops"
    
    # Check if already initialized
    if promptops_dir.exists():
        console.print(f"[yellow]⚠️  PromptOps project already initialized in {project_root}[/yellow]")
        if not typer.confirm("Reinitialize?"):
            raise typer.Abort()
    
    # Create .promptops directory structure
    promptops_dir.mkdir(exist_ok=True)
    (promptops_dir / "staged").mkdir(exist_ok=True)
    (promptops_dir / "config").mkdir(exist_ok=True)
    
    # Create config file
    config = {
        "version": "0.1.0",
        "project_name": project_root.name,
        "author": os.getenv("USER") or os.getenv("USERNAME") or "unknown",
        "default_branch": "main",
        "auto_eval": True,
        "eval_threshold": {
            "accuracy": 0.85,
            "hallucination": 0.85,
            "relevance": 0.80
        }
    }
    
    config_file = promptops_dir / "config" / "promptops.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    
    # Create .gitignore for .promptops if using Git
    gitignore_file = promptops_dir / ".gitignore"
    with open(gitignore_file, "w") as f:
        f.write("staged/*\n")
        f.write("*.tmp\n")
    
    # Success message
    console.print()
    console.print(Panel.fit(
        f"[green]✅ Initialized PromptOps project in {project_root}[/green]\n\n"
        f"[cyan]Configuration:[/cyan]\n"
        f"  • Project: {config['project_name']}\n"
        f"  • Author: {config['author']}\n"
        f"  • Auto-eval: {config['auto_eval']}\n\n"
        f"[yellow]Next steps:[/yellow]\n"
        f"  1. Create a prompt YAML file (see prompts/templates/)\n"
        f"  2. Run: promptops add <file>\n"
        f"  3. Run: promptops commit -m 'Initial version'",
        title="🚀 PromptOps Initialized",
        border_style="green"
    ))


def add_command(files: list[str]):
    """
    Stage files for commit
    """
    promptops_dir = Path.cwd() / ".promptops"
    
    if not promptops_dir.exists():
        console.print("[red]❌ Not a PromptOps project. Run 'promptops init' first.[/red]")
        raise typer.Exit(1)
    
    staged_dir = promptops_dir / "staged"
    staged_files = []
    
    for file_pattern in files:
        matched_files = list(Path.cwd().glob(file_pattern))
        
        if not matched_files:
            console.print(f"[yellow]⚠️  No files matched: {file_pattern}[/yellow]")
            continue
        
        for file_path in matched_files:
            if not file_path.is_file():
                continue
            
            if not file_path.suffix in [".yaml", ".yml"]:
                console.print(f"[yellow]⚠️  Skipping non-YAML file: {file_path.name}[/yellow]")
                continue
            
            # Copy to staged directory
            import shutil
            dest = staged_dir / file_path.name
            shutil.copy2(file_path, dest)
            staged_files.append(file_path.name)
            console.print(f"[green]✓[/green] Staged: {file_path.name}")
    
    if staged_files:
        console.print(f"\n[cyan]Staged {len(staged_files)} file(s)[/cyan]")
        console.print("[dim]Run 'promptops commit -m \"message\"' to commit[/dim]")
    else:
        console.print("[yellow]No files were staged[/yellow]")


def commit_command(message: str, author: Optional[str] = None):
    """
    Commit staged prompts
    """
    from promptops.core.versioning import (
        SessionLocal, parse_prompt_file, create_version, get_current_head
    )
    
    promptops_dir = Path.cwd() / ".promptops"
    
    if not promptops_dir.exists():
        console.print("[red]❌ Not a PromptOps project. Run 'promptops init' first.[/red]")
        raise typer.Exit(1)
    
    # Load config for default author
    config_file = promptops_dir / "config" / "promptops.json"
    with open(config_file) as f:
        config = json.load(f)
    
    author = author or config.get("author", "unknown")
    
    # Get staged files
    staged_dir = promptops_dir / "staged"
    staged_files = list(staged_dir.glob("*.y*ml"))
    
    if not staged_files:
        console.print("[yellow]⚠️  No files staged for commit[/yellow]")
        console.print("[dim]Run 'promptops add <file>' first[/dim]")
        raise typer.Exit(1)
    
    # Process each staged file
    db = SessionLocal()
    committed_versions = []
    
    try:
        with console.status("[cyan]Committing...[/cyan]"):
            for file_path in staged_files:
                # Parse prompt file
                parsed = parse_prompt_file(file_path)
                
                # Get current HEAD for parent reference
                current_head = get_current_head(db, config["project_name"])
                parent_id = current_head.id if current_head else None
                
                # Create version
                version = create_version(
                    content=parsed["content"],
                    metadata=parsed["metadata"],
                    tags=parsed["tags"],
                    author=author,
                    message=message,
                    db=db,
                    parent_id=parent_id,
                )
                
                committed_versions.append((file_path.name, version))
        
        # Success output
        console.print()
        table = Table(title="✅ Commit Successful", box=box.ROUNDED, show_header=True)
        table.add_column("File", style="cyan")
        table.add_column("Hash", style="green")
        table.add_column("Parent", style="dim")
        
        for filename, version in committed_versions:
            parent_hash = version.parent.hash[:8] if version.parent else "—"
            table.add_row(
                filename,
                version.hash[:8],
                parent_hash
            )
        
        console.print(table)
        console.print(f"\n[green]Author:[/green] {author}")
        console.print(f"[green]Message:[/green] {message}")
        console.print(f"[green]Versions:[/green] {len(committed_versions)}")
        
        # Clear staged files
        for file_path in staged_files:
            file_path.unlink()
        
        console.print("\n[dim]Staged files cleared[/dim]")
        
    except Exception as e:
        console.print(f"\n[red]❌ Commit failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)
    finally:
        db.close()


def log_command(limit: int = 10, oneline: bool = False):
    """
    Show commit history
    """
    from promptops.core.versioning import SessionLocal, get_version_history
    
    promptops_dir = Path.cwd() / ".promptops"
    
    if not promptops_dir.exists():
        console.print("[red]❌ Not a PromptOps project. Run 'promptops init' first.[/red]")
        raise typer.Exit(1)
    
    db = SessionLocal()
    
    try:
        versions = get_version_history(db, limit=limit)
        
        if not versions:
            console.print("[yellow]No commits yet[/yellow]")
            return
        
        console.print()
        
        if oneline:
            # Compact format
            for v in versions:
                msg = v.prompt_metadata.get("commit_message", "No message")  # FIXED
                console.print(f"[green]{v.hash[:8]}[/green] {msg[:60]} [dim]({v.author})[/dim]")
        else:
            # Full format
            for i, v in enumerate(versions):
                if i > 0:
                    console.print()
                
                console.print(f"[yellow]commit[/yellow] [green]{v.hash}[/green]")
                if v.parent:
                    console.print(f"[dim]Parent: {v.parent.hash[:8]}[/dim]")
                console.print(f"Author: {v.author}")
                console.print(f"Date:   {v.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                console.print()
                msg = v.prompt_metadata.get("commit_message", "No message")  # FIXED
                console.print(f"    {msg}")
                
                # Show tags if any
                if v.tags:
                    console.print(f"    [cyan]Tags:[/cyan] {', '.join(v.tags)}")
        
        console.print()
        
    finally:
        db.close()


def diff_command(version_a: str, version_b: Optional[str] = None):
    """
    Show diff between versions
    """
    from promptops.core.versioning import (
        SessionLocal, get_version_by_hash, get_current_head, get_diff
    )
    
    db = SessionLocal()
    
    try:
        # Resolve version A
        if version_a.lower() == "head":
            ver_a = get_current_head(db)
        else:
            ver_a = get_version_by_hash(db, version_a)
        
        if not ver_a:
            console.print(f"[red]❌ Version not found: {version_a}[/red]")
            raise typer.Exit(1)
        
        # Resolve version B (default to current HEAD)
        if version_b:
            if version_b.lower() == "head":
                ver_b = get_current_head(db)
            else:
                ver_b = get_version_by_hash(db, version_b)
        else:
            ver_b = get_current_head(db)
        
        if not ver_b:
            console.print(f"[red]❌ Version not found: {version_b}[/red]")
            raise typer.Exit(1)
        
        # Compute diff
        diff_data = get_diff(ver_a, ver_b)
        
        # Display
        console.print()
        console.print(f"[yellow]diff[/yellow] {ver_a.hash[:8]} → {ver_b.hash[:8]}")
        console.print(f"[dim]From: {ver_a.author} at {ver_a.timestamp}[/dim]")
        console.print(f"[dim]To:   {ver_b.author} at {ver_b.timestamp}[/dim]")
        console.print()
        
        diff_text = "\n".join(diff_data["diff_lines"])
        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
        console.print(syntax)
        console.print()
        
    finally:
        db.close()


def status_command():
    """
    Show working directory status
    """
    promptops_dir = Path.cwd() / ".promptops"
    
    if not promptops_dir.exists():
        console.print("[red]❌ Not a PromptOps project. Run 'promptops init' first.[/red]")
        raise typer.Exit(1)
    
    staged_dir = promptops_dir / "staged"
    staged_files = list(staged_dir.glob("*.y*ml"))
    
    console.print()
    table = Table(title="Working Directory Status", show_header=True, header_style="bold cyan")
    table.add_column("Status", style="green")
    table.add_column("File", style="white")
    
    if staged_files:
        for f in staged_files:
            table.add_row("staged", f.name)
    else:
        table.add_row("[dim]—[/dim]", "[dim]No staged files[/dim]")
    
    console.print(table)
    console.print()


def rollback_command(steps: int = 1, force: bool = False):
    """
    Rollback to previous version
    """
    console.print("[yellow]🚧 Rollback command coming soon...[/yellow]")




def deploy_command(environment: str, version_hash: Optional[str], author: Optional[str]):
    """Deploy a prompt version to an environment"""
    from promptops.core.versioning import SessionLocal, get_current_head, get_version_by_hash
    from promptops.core.models import Deployment
    from promptops.deploy.engine import DeploymentEngine
    from datetime import datetime
    
    valid_envs = ["dev", "staging", "prod"]
    if environment not in valid_envs:
        console.print(f"[red]❌ Invalid environment: {environment}[/red]")
        console.print(f"[dim]Valid options: {', '.join(valid_envs)}[/dim]")
        raise typer.Exit(1)
    
    db = SessionLocal()
    
    try:
        promptops_dir = Path.cwd() / ".promptops"
        if promptops_dir.exists():
            config_file = promptops_dir / "config" / "promptops.json"
            with open(config_file) as f:
                config = json.load(f)
            author = author or config.get("author", "unknown")
        else:
            author = author or "unknown"
        
        if version_hash:
            version = get_version_by_hash(db, version_hash)
            if not version:
                console.print(f"[red]❌ Version not found: {version_hash}[/red]")
                raise typer.Exit(1)
        else:
            version = get_current_head(db)
            if not version:
                console.print("[red]❌ No versions found. Commit a prompt first.[/red]")
                raise typer.Exit(1)
        
        if environment == "prod":
            console.print(f"\n[yellow]⚠️  You are about to deploy to PRODUCTION[/yellow]")
            console.print(f"[dim]Version: {version.hash[:8]}[/dim]")
            console.print(f"[dim]Message: {version.prompt_metadata.get('commit_message', 'N/A')}[/dim]\n")
            
            if not typer.confirm("Continue?"):
                console.print("[yellow]Deployment cancelled[/yellow]")
                raise typer.Abort()
        
        with console.status(f"[cyan]Deploying to {environment}...[/cyan]"):
            current = db.query(Deployment)\
                .filter(Deployment.environment == environment)\
                .filter(Deployment.is_active == True)\
                .all()
            
            for dep in current:
                dep.is_active = False
            
            deployment = Deployment(
                version_id=version.id,
                environment=environment,
                deployed_by=author,
                deployed_at=datetime.utcnow(),
                is_active=True
            )
            
            db.add(deployment)
            db.commit()
            db.refresh(deployment)
            
            engine = DeploymentEngine()
            engine.invalidate_cache(environment)
        
        console.print()
        console.print(Panel.fit(
            f"[green]✅ Deployment Successful[/green]\n\n"
            f"[cyan]Version:[/cyan] {version.hash[:8]}\n"
            f"[cyan]Environment:[/cyan] {environment}\n"
            f"[cyan]Deployed by:[/cyan] {author}\n"
            f"[cyan]Time:[/cyan] {deployment.deployed_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"[dim]Apps can now fetch via: GET /prompts/{environment}/active[/dim]",
            title="🚀 Deployed",
            border_style="green"
        ))
        
    except Exception as e:
        console.print(f"\n[red]❌ Deployment failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)
    finally:
        db.close()


def serve_command(host: str, port: int, reload: bool):
    """Start the FastAPI server"""
    import uvicorn
    
    console.print()
    console.print(Panel.fit(
        f"[cyan]Starting PromptOps API Server[/cyan]\n\n"
        f"[green]URL:[/green] http://{host}:{port}\n"
        f"[green]Docs:[/green] http://{host}:{port}/docs\n"
        f"[green]Health:[/green] http://{host}:{port}/health\n\n"
        f"[dim]Press Ctrl+C to stop[/dim]",
        title="🚀 PromptOps API",
        border_style="cyan"
    ))
    console.print()
    
    try:
        uvicorn.run(
            "promptops.api.app:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")


"""
Add this function to your commands.py file
"""

def eval_command(run: bool, version_hash: Optional[str], compare: bool, samples: int):
    """
    Run evaluation on a prompt version
    """
    import asyncio
    from promptops.core.versioning import SessionLocal, get_current_head, get_version_by_hash
    from promptops.eval.engine import EvaluationEngine
    from promptops.eval.scorers import create_default_scorers
    
    db = SessionLocal()
    
    try:
        # Determine which version to evaluate
        if version_hash:
            version = get_version_by_hash(db, version_hash)
            if not version:
                console.print(f"[red]❌ Version not found: {version_hash}[/red]")
                raise typer.Exit(1)
        else:
            version = get_current_head(db)
            if not version:
                console.print("[red]❌ No versions found. Commit a prompt first.[/red]")
                raise typer.Exit(1)
        
        if not run:
            console.print("[yellow]Add --run flag to execute evaluation[/yellow]")
            console.print(f"[dim]Would evaluate version: {version.hash[:8]}[/dim]")
            return
        
        console.print(f"\n[cyan]🔍 Evaluating version {version.hash[:8]}...[/cyan]\n")
        
        # Create evaluation engine
        engine = EvaluationEngine(db)
        
        # Register scorers
        for scorer in create_default_scorers():
            engine.register_scorer(scorer)
        
        # Run evaluation
        with console.status("[cyan]Running evaluation pipeline...[/cyan]"):
            result = asyncio.run(engine.evaluate(version, num_samples=samples))
        
        # Display results
        console.print()
        table = Table(title="📊 Evaluation Results", box=box.ROUNDED, show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Score", style="white")
        table.add_column("Status", style="white")
        
        def get_status(score, threshold, higher_is_better=True):
            if score is None:
                return "[dim]N/A[/dim]"
            if higher_is_better:
                return "[green]✓ Pass[/green]" if score >= threshold else "[red]✗ Fail[/red]"
            else:
                return "[green]✓ Pass[/green]" if score <= threshold else "[red]✗ Fail[/red]"
        
        metrics = [
            ("Accuracy", result.score_accuracy, 0.85, True, "{}"),
            ("Hallucination", result.score_hallucination, 0.85, True, "{}"),
            ("Relevance", result.score_relevance, 0.80, True, "{}"),
            ("Latency (p95)", result.score_latency_p95, 2000, False, "{:.0f} ms"),
            ("Consistency", result.score_consistency, 0.75, True, "{}"),
        ]
        
        for name, score, threshold, higher_better, fmt in metrics:
            if score is not None:
                if "ms" in fmt:
                    score_str = fmt.format(score)
                else:
                    score_str = f"{score:.2f}"
            else:
                score_str = "—"
            
            status = get_status(score, threshold, higher_better)
            table.add_row(name, score_str, status)
        
        console.print(table)
        console.print()
        
        # Overall pass/fail
        all_pass = all([
            result.score_accuracy and result.score_accuracy >= 0.85,
            result.score_hallucination and result.score_hallucination >= 0.85,
            result.score_relevance and result.score_relevance >= 0.80,
            result.score_latency_p95 and result.score_latency_p95 <= 2000,
            result.score_consistency and result.score_consistency >= 0.75,
        ])
        
        if all_pass:
            console.print("[green]✅ All metrics passed! This version is ready to deploy.[/green]")
        else:
            console.print("[yellow]⚠️  Some metrics failed. Review before deploying.[/yellow]")
        
        # Compare with parent if requested
        if compare and version.parent_id:
            console.print(f"\n[cyan]📈 Comparing with parent version...[/cyan]\n")
            
            comparison = engine.compare_versions(version.parent_id, version.id)
            
            comp_table = Table(title="Delta vs Parent", box=box.SIMPLE, show_header=True)
            comp_table.add_column("Metric", style="cyan")
            comp_table.add_column("Change", style="white")
            comp_table.add_column("Assessment", style="white")
            
            for metric, delta in comparison["deltas"].items():
                if metric == "latency_p95":
                    change_str = f"{delta:+.0f} ms"
                    assessment = "[green]↓ Better[/green]" if delta < 0 else "[red]↑ Worse[/red]"
                else:
                    change_str = f"{delta:+.2f}"
                    assessment = "[green]↑ Better[/green]" if delta > 0 else "[red]↓ Worse[/red]"
                
                comp_table.add_row(metric.replace("_", " ").title(), change_str, assessment)
            
            console.print(comp_table)
            
            if comparison["regression_detected"]:
                console.print("\n[red]⚠️  REGRESSION DETECTED - Score dropped significantly[/red]")
            else:
                console.print("\n[green]✓ No regressions detected[/green]")
        
        console.print()
        
    except Exception as e:
        console.print(f"\n[red]❌ Evaluation failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)
    finally:
        db.close()

