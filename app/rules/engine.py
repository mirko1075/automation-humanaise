# app/rules/engine.py
"""
Rules engine for PREVENTIVI pipeline.
- Evaluates JSON-based rulesets for triage and actions.
- Supports all/any, eq/neq/in/gte/lte/contains, dotted field paths.
- Applies actions: set, tag, enqueue.
- Writes audit to rule_runs table only.
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import Ruleset, Rule, RuleRun, RulesetScopeEnum
from sqlalchemy import and_, desc

logger = logging.getLogger(__name__)

# --- DSL helpers ---
def get_dotted(context: dict, path: str) -> Any:
    parts = path.split('.')
    val = context
    for p in parts:
        if isinstance(val, dict) and p in val:
            val = val[p]
        else:
            return None
    return val

def op_eval(op: str, a: Any, b: Any) -> bool:
    if op == 'eq':
        return a == b
    if op == 'neq':
        return a != b
    if op == 'in':
        return a in b if isinstance(b, (list, set)) else False
    if op == 'gte':
        return a >= b
    if op == 'lte':
        return a <= b
    if op == 'contains':
        return b in a if isinstance(a, (str, list)) else False
    return False

def evaluate_match(match: dict, context: dict) -> bool:
    """
    Evaluate match dict against context.
    Supports 'all', 'any' with conditions.
    """
    if not match:
        return True
    if 'all' in match:
        if not all(evaluate_match(cond, context) for cond in match['all']):
            return False
    if 'any' in match:
        if not any(evaluate_match(cond, context) for cond in match['any']):
            return False
    if 'field' in match and 'op' in match and 'value' in match:
        val = get_dotted(context, match['field'])
        return op_eval(match['op'], val, match['value'])
    return True

def apply_actions(actions: List[dict], context: dict) -> dict:
    """
    Apply actions to context. Mutates context in-place.
    Supported: set, tag, enqueue.
    """
    for action in actions:
        if 'set' in action:
            path = action['set']['path']
            value = action['set']['value']
            parts = path.split('.')
            d = context
            for p in parts[:-1]:
                if p not in d or not isinstance(d[p], dict):
                    d[p] = {}
                d = d[p]
            d[parts[-1]] = value
        elif 'tag' in action:
            tag = action['tag']
            context.setdefault('tags', []).append(tag)
        elif 'enqueue' in action:
            context.setdefault('planned_actions', []).append(action['enqueue'])
    return context

def run_ruleset(
    db: Session,
    tenant_id: str,
    scope: str,
    normalized_event_id: UUID,
    context: dict
) -> dict:
    """
    Run ruleset for tenant_id and scope. Writes rule_runs audit.
    Returns: {
      'matched_rules': [...],
      'tags': [...],
      'planned_actions': [...],
      'final_context': {...}
    }
    """
    logger.info(f"Running ruleset for tenant={tenant_id} scope={scope} event={normalized_event_id}")
    # Load active ruleset (highest version)
    ruleset = db.query(Ruleset).filter(
        Ruleset.tenant_id == tenant_id,
        Ruleset.scope == scope,
        Ruleset.active == True
    ).order_by(desc(Ruleset.version)).first()
    if not ruleset:
        logger.warning(f"No active ruleset for tenant={tenant_id} scope={scope}")
        return {'matched_rules': [], 'tags': [], 'planned_actions': [], 'final_context': context}
    rules = db.query(Rule).filter(
        Rule.ruleset_id == ruleset.id,
        Rule.enabled == True
    ).order_by(Rule.priority.asc()).all()
    matched_rules = []
    for rule in rules:
        if evaluate_match(rule.match, context):
            logger.debug(f"Rule matched: {rule.name}")
            matched_rules.append(rule.name)
            context = apply_actions(rule.actions, context)
    tags = context.get('tags', [])
    planned_actions = context.get('planned_actions', [])
    result = {
        'matched_rules': matched_rules,
        'tags': tags,
        'planned_actions': planned_actions,
        'final_context': context
    }
    # Audit
    rule_run = RuleRun(
        tenant_id=tenant_id,
        normalized_event_id=normalized_event_id,
        ruleset_scope=scope,
        ruleset_version=ruleset.version,
        result=result,
        executed_at=datetime.utcnow()
    )
    db.add(rule_run)
    db.commit()
    logger.info(f"RuleRun audit written for event={normalized_event_id}")
    return result
