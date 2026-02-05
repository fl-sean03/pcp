# PCP Self-Reflection Session

You are conducting a self-reflection session for the Personal Control Plane (PCP). Your mission is to deeply analyze how PCP is being used, identify opportunities for improvement, and propose changes ranging from quick fixes to architectural overhauls.

## Your Mission

1. **Understand the Vision**: Read VISION.md deeply. This is what PCP is becoming - an AI system that extends the user's memory, understands his context, takes action on the user's behalf, and gets smarter over time.

2. **Assess Current State**: Review CLAUDE.md and explore the codebase. Understand what PCP can actually do today.

3. **Analyze Real Usage**: Study the Discord conversations and vault data. How does the user actually use PCP? What works? What doesn't?

4. **Identify Opportunities**: Find gaps between vision and reality. Spot friction, underutilized potential, missing capabilities.

5. **Propose Improvements**: From quick wins to architectural changes. Be specific and actionable.

6. **Think Beyond**: Suggest things the user wouldn't have thought of. What could transform PCP?

## Context Files

You have access to:

1. **VISION.md**: The north star - what PCP should ultimately become
2. **CLAUDE.md**: Current capabilities and how PCP works today
3. **Usage Data**: Discord conversations from the analysis period (in the context JSON)
4. **Vault Snapshot**: Current state of captures, tasks, knowledge, people, projects
5. **Previous Reflections**: Past analyses and their outcomes (if any)
6. **Friction Events**: Detected points of user frustration
7. **Capability Gaps**: Record of what PCP tried but couldn't do, and self-improvement attempts

## Analysis Framework

### Phase 1: Vision Alignment

Read VISION.md carefully. Then assess:

- **What's working well?** Which aspects of the vision are already implemented effectively?
- **What's missing?** Which vision goals are underdeveloped or not started?
- **What's bloat?** Are there capabilities that don't serve the vision?
- **What would close the gap?** Specific changes to move closer to the vision.

Key vision principles to evaluate against:
- Zero friction - just talk naturally, no commands needed
- Universal capture - everything gets captured, understood, connected
- Contextual memory - semantic search, knows people/projects/history
- Proactive intelligence - adds value without being asked
- Self-evolution - learns and adapts to the user's patterns

### Phase 2: Usage Pattern Analysis

Carefully read through the Discord conversations. Look for:

**Repeated Patterns**
- What does the user ask for frequently?
- What phrases or patterns recur?
- What workflows get triggered often?

**Friction Points**
- Where did the user retry or clarify?
- What error messages appeared?
- Where did PCP misunderstand intent?
- What took multiple attempts?

**Manual Workarounds**
- What is the user doing manually that PCP could automate?
- What steps does the user repeat that could be streamlined?

**Underutilized Features**
- What capabilities exist but the user rarely uses?
- Why might features be underutilized?

**Missing Capabilities**
- What does the user ask for that doesn't exist?
- What implicit needs are revealed in conversations?

**Language Patterns**
- How does the user naturally phrase things?
- What vocabulary or shortcuts does the user use?
- How can PCP better match the user's communication style?

### Phase 3: Technical Assessment

Explore the codebase (use Read, Grep, Glob tools). Assess:

- **Code quality**: Maintainability, clarity, consistency
- **Architecture**: Is the structure serving the vision?
- **Performance**: Any obvious bottlenecks?
- **Error handling**: Are failures graceful?
- **Testing**: What's covered? What's not?
- **Documentation**: Is CLAUDE.md accurate and complete?

### Phase 4: Capability Gap Analysis

Review the capability_gaps data in the context. This tracks what PCP tried but couldn't do:

**Gap Patterns**
- What capabilities are missing? (unresolved gaps)
- Which gaps recur frequently? (top patterns)
- Are there patterns suggesting new skills to create?

**Resolution Effectiveness**
- What's the resolution rate? (should be improving over time)
- What types of gaps tend to fail resolution?
- Are user-pending gaps being addressed?

**Proactive Skill Creation**
- Based on gap patterns, what skills should be created preemptively?
- Which integrations should be set up before the user needs them?
- Are there CLI tools frequently missing that should be installed?

**Risk Assessment**
- Are high-risk capabilities being properly guarded?
- Are low-risk acquisitions happening automatically as expected?

Include capability gap recommendations in your structured output.

### Phase 5: Creative Exploration

Think freely beyond current constraints:

- **10x improvement**: What would make PCP 10x more valuable?
- **Obvious improvement**: What's the "obvious" change no one has suggested?
- **Surprise and delight**: What would exceed the user's expectations?
- **Transformative integrations**: What new capabilities would be game-changing?
- **Learning and adaptation**: How could PCP better learn from interactions?
- **Future-proofing**: What would make PCP more extensible?

## Output Format

You must produce TWO outputs:

### 1. Markdown Report

Write a human-readable markdown report saved to the specified output file with these sections:
- Executive Summary (5-7 bullets, health assessment, top 3 priorities)
- Vision Alignment (working well, gaps, opportunities)
- Usage Analysis (patterns, friction, feature utilization)
- Quick Wins (< 30 min each)
- Medium Improvements (1-4 hours each)
- Major Proposals (1+ days)
- Wild Ideas (exploratory)
- Anti-Recommendations (what to avoid)

### 2. Structured JSON

**CRITICAL**: In addition to the markdown, output a JSON block at the END of your report with ALL recommendations in structured format. This allows programmatic tracking.

Format the JSON block like this:

```json
{
  "summary": {
    "health": "healthy|needs_attention|concerning",
    "top_priorities": ["priority 1", "priority 2", "priority 3"],
    "key_findings": ["finding 1", "finding 2"]
  },
  "recommendations": [
    {
      "id": "QW-1",
      "category": "quick_win",
      "title": "Short descriptive title",
      "observation": "What you noticed",
      "evidence": "Specific messages/data that support this",
      "proposal": "The concrete change to make",
      "implementation": "Step-by-step how to implement",
      "files": ["file1.py", "file2.py"],
      "effort": "15min"
    },
    {
      "id": "MI-1",
      "category": "medium_improvement",
      "title": "...",
      "observation": "...",
      "evidence": "...",
      "proposal": "...",
      "implementation": "...",
      "files": ["..."],
      "effort": "2h",
      "testing": "How to test this change",
      "rollback": "How to undo if needed"
    },
    {
      "id": "MP-1",
      "category": "major_proposal",
      "title": "...",
      "observation": "...",
      "evidence": "...",
      "proposal": "...",
      "implementation": "...",
      "files": ["..."],
      "effort": "2d",
      "architecture_impact": "What this changes architecturally",
      "migration": "Migration steps if needed",
      "risk": "Risks and mitigations"
    },
    {
      "id": "WI-1",
      "category": "wild_idea",
      "title": "...",
      "description": "Full description of the idea",
      "potential_impact": "What this could enable",
      "research_needed": "What to investigate first"
    },
    {
      "id": "ANTI-1",
      "category": "anti_recommendation",
      "title": "What NOT to do",
      "reason": "Why this should be avoided"
    },
    {
      "id": "CG-1",
      "category": "capability_gap",
      "title": "Proactive capability to acquire",
      "gap_pattern": "Pattern ID if known",
      "justification": "Why this capability should be added",
      "risk_level": "low|medium|high",
      "implementation": "How to acquire this capability"
    }
  ]
}
```

**Category values**: `quick_win`, `medium_improvement`, `major_proposal`, `wild_idea`, `anti_recommendation`, `capability_gap`

**ID format**: `QW-N`, `MI-N`, `MP-N`, `WI-N`, `ANTI-N` (numbered sequentially within category)

## Guidelines

### Be Specific
- Reference actual messages from Discord history
- Cite line numbers when discussing code
- Provide concrete examples, not abstractions

### Be Actionable
- Every recommendation should be implementable
- Include file paths, function names, specific changes
- Estimate effort realistically

### Be Honest
- If something is working well, acknowledge it
- If something is broken, say so clearly
- Don't inflate issues or solutions

### Think Independently
- Don't just echo what's in the docs
- Form your own assessment based on evidence
- Challenge assumptions if warranted

### Consider Tradeoffs
- Every change has costs
- Acknowledge complexity, maintenance burden
- Weigh benefits against drawbacks

### Prioritize Ruthlessly
- What matters most right now?
- What can wait?
- What should never be done?

## Remember PCP's Philosophy

These principles should guide all recommendations:

1. **Minimal hardcoded rules** - Claude handles intelligence, not rigid patterns
2. **Zero friction** - Just talk naturally, no command syntax
3. **Proactive value** - Add insight without being asked
4. **Continuous evolution** - Learn and adapt over time
5. **Agentic execution** - Delegate heavy work, respond quickly to simple requests

Your recommendations should align with and reinforce these principles.

## Begin Analysis

Start by reading the VISION.md and CLAUDE.md files to understand the intended design. Then analyze the usage data to understand actual usage. Compare the two to identify opportunities.

Focus on changes that would genuinely improve the user's experience with PCP. Prioritize impact over cleverness. The goal is a more effective external brain, not a more complex one.
