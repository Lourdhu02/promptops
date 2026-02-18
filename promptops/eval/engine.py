
"""
Evaluation Engine - Core orchestrator for prompt quality scoring
"""
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from promptops.core.models import PromptVersion, EvalResult, Dataset


class EvaluationEngine:
    """
    Orchestrates the evaluation of a prompt version
    Runs all scorers and aggregates results
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.scorers = []
    
    def register_scorer(self, scorer):
        """Register a scorer to be run during evaluation"""
        self.scorers.append(scorer)
    
    async def evaluate(
        self,
        version: PromptVersion,
        dataset_id: Optional[UUID] = None,
        num_samples: int = 10,
    ) -> EvalResult:
        """
        Run full evaluation pipeline on a prompt version
        
        Args:
            version: The PromptVersion to evaluate
            dataset_id: Optional dataset to evaluate against
            num_samples: Number of test samples to run
        
        Returns:
            EvalResult with all scores
        """
        scores = {}
        
        # Run each scorer
        for scorer in self.scorers:
            try:
                score = await scorer.score(
                    prompt=version.content,
                    metadata=version.prompt_metadata,
                    num_samples=num_samples
                )
                scores[scorer.name] = score
            except Exception as e:
                print(f"Warning: Scorer {scorer.name} failed: {e}")
                scores[scorer.name] = None
        
        # Create EvalResult
        result = EvalResult(
            version_id=version.id,
            score_accuracy=scores.get("accuracy"),
            score_hallucination=scores.get("hallucination"),
            score_relevance=scores.get("relevance"),
            score_latency_p95=scores.get("latency_p95"),
            score_consistency=scores.get("consistency"),
            dataset_id=dataset_id,
            created_at=datetime.utcnow()
        )
        
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        
        return result
    
    def get_results(self, version_id: UUID) -> List[EvalResult]:
        """Get all evaluation results for a version"""
        return self.db.query(EvalResult)\
            .filter(EvalResult.version_id == version_id)\
            .all()
    
    def compare_versions(
        self,
        version_a_id: UUID,
        version_b_id: UUID
    ) -> Dict[str, Any]:
        """
        Compare evaluation results between two versions
        Useful for regression detection
        """
        results_a = self.get_results(version_a_id)
        results_b = self.get_results(version_b_id)
        
        if not results_a or not results_b:
            return {"error": "Missing evaluation results"}
        
        # Take the most recent result for each
        latest_a = results_a[-1]
        latest_b = results_b[-1]
        
        comparison = {
            "version_a": str(version_a_id),
            "version_b": str(version_b_id),
            "deltas": {
                "accuracy": (latest_b.score_accuracy or 0) - (latest_a.score_accuracy or 0),
                "hallucination": (latest_b.score_hallucination or 0) - (latest_a.score_hallucination or 0),
                "relevance": (latest_b.score_relevance or 0) - (latest_a.score_relevance or 0),
                "latency_p95": (latest_b.score_latency_p95 or 0) - (latest_a.score_latency_p95 or 0),
                "consistency": (latest_b.score_consistency or 0) - (latest_a.score_consistency or 0),
            },
            "regression_detected": False
        }
        
        # Check for regressions (score drops > 5%)
        for metric, delta in comparison["deltas"].items():
            if metric == "latency_p95":
                # For latency, increase is bad
                if delta > 200:  # 200ms increase
                    comparison["regression_detected"] = True
            else:
                # For other metrics, decrease is bad
                if delta < -0.05:  # 5% drop
                    comparison["regression_detected"] = True
        
        return comparison


class BaseScorer:
    """Base class for all scorers"""
    
    def __init__(self, name: str):
        self.name = name
    
    async def score(
        self,
        prompt: str,
        metadata: Dict[str, Any],
        num_samples: int = 10
    ) -> float:
        """
        Score a prompt
        Must be implemented by subclasses
        Returns a score between 0 and 1 (or latency in ms)
        """
        raise NotImplementedError