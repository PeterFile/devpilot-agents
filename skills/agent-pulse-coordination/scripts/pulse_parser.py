"""
PULSE Document Parser and Generator

Parses and generates PROJECT_PULSE.md documents for structured human-layer document processing.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class MentalModel:
    """Structured representation of Mental Model section"""
    description: str  # One-sentence project description
    mermaid_diagram: str  # Mermaid code


@dataclass
class RisksAndDebt:
    """Structured representation of Risks & Debt section"""
    cognitive_warnings: List[str] = field(default_factory=list)
    technical_debt: List[str] = field(default_factory=list)
    pending_decisions: List[str] = field(default_factory=list)


@dataclass
class SemanticAnchor:
    """Structured representation of a semantic anchor"""
    module: str
    path: str
    symbol: str


@dataclass
class PulseDocument:
    """Complete structured representation of a PULSE document"""
    mental_model: MentalModel
    narrative_delta: str
    risks_and_debt: RisksAndDebt
    semantic_anchors: List[SemanticAnchor]


@dataclass
class ParseError:
    """Parse error"""
    section: str
    message: str


@dataclass
class ParseResult:
    """Parse result"""
    valid: bool
    document: Optional[PulseDocument] = None
    errors: List[ParseError] = field(default_factory=list)


# 四个必需节的标题模式
SECTION_PATTERNS = {
    'mental_model': r'^##\s*🟢?\s*Mental\s*Model',
    'narrative_delta': r'^##\s*🟡?\s*Narrative\s*Delta',
    'risks_and_debt': r'^##\s*🔴?\s*Risks\s*[&＆]\s*Debt',
    'semantic_anchors': r'^##\s*🔗?\s*Semantic\s*Anchors',
}

REQUIRED_SECTIONS = ['mental_model', 'narrative_delta', 'risks_and_debt', 'semantic_anchors']


def _find_sections(content: str) -> dict:
    """
    Find positions and content of each section in the document
    
    Returns:
        dict: {section_name: content}
    """
    lines = content.split('\n')
    sections = {}
    current_section = None
    current_start = 0
    current_lines = []
    
    for i, line in enumerate(lines):
        # 检查是否是新节的开始
        found_section = None
        for section_name, pattern in SECTION_PATTERNS.items():
            if re.match(pattern, line, re.IGNORECASE):
                found_section = section_name
                break
        
        if found_section:
            # 保存前一节
            if current_section:
                sections[current_section] = '\n'.join(current_lines)
            
            current_section = found_section
            current_start = i
            current_lines = [line]
        elif current_section:
            current_lines.append(line)
    
    # 保存最后一节
    if current_section:
        sections[current_section] = '\n'.join(current_lines)
    
    return sections


def _parse_mental_model(content: str) -> Tuple[Optional[MentalModel], List[ParseError]]:
    """Parse Mental Model section"""
    errors = []
    
    # 提取 Mermaid 图
    mermaid_match = re.search(r'```mermaid\s*(.*?)```', content, re.DOTALL)
    if not mermaid_match:
        errors.append(ParseError('Mental Model', 'Missing Mermaid diagram'))
        mermaid_diagram = ''
    else:
        mermaid_diagram = mermaid_match.group(1).strip()
    
    # 提取描述（Mermaid 之前的非空行，排除标题和注释）
    lines_before_mermaid = content.split('```mermaid')[0] if '```mermaid' in content else content
    description_lines = []
    for line in lines_before_mermaid.split('\n'):
        line = line.strip()
        # 跳过标题、空行、注释
        if line and not line.startswith('#') and not line.startswith('<!--'):
            # 跳过注释结束
            if '-->' in line:
                continue
            description_lines.append(line)
    
    description = ' '.join(description_lines).strip()
    if not description:
        # 如果没有找到描述，尝试从方括号中提取
        bracket_match = re.search(r'\[([^\]]+)\]', lines_before_mermaid)
        if bracket_match:
            description = bracket_match.group(1).strip()
    
    if not description:
        errors.append(ParseError('Mental Model', 'Missing project description'))
    
    if errors:
        return None, errors
    
    return MentalModel(description=description, mermaid_diagram=mermaid_diagram), []


def _parse_narrative_delta(content: str) -> Tuple[str, List[ParseError]]:
    """Parse Narrative Delta section"""
    # Remove header lines and comments
    lines = []
    in_comment = False
    for line in content.split('\n'):
        if '<!--' in line:
            in_comment = True
        if in_comment:
            if '-->' in line:
                in_comment = False
            continue
        if not re.match(r'^##', line):
            lines.append(line)
    
    narrative = '\n'.join(lines).strip()
    return narrative, []


def _parse_risks_and_debt(content: str) -> Tuple[Optional[RisksAndDebt], List[ParseError]]:
    """Parse Risks & Debt section"""
    cognitive_warnings = []
    technical_debt = []
    pending_decisions = []
    
    current_subsection = None
    
    for line in content.split('\n'):
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        
        # Detect subsection headers (must start with ### or **)
        if line_stripped.startswith('###') or line_stripped.startswith('**'):
            if 'cognitive' in line_lower:
                current_subsection = 'cognitive'
                continue
            elif 'technical debt' in line_lower:
                current_subsection = 'debt'
                continue
            elif 'pending' in line_lower:
                current_subsection = 'pending'
                continue
        
        # Extract list items
        list_match = re.match(r'^[-*]\s+(.+)$', line_stripped)
        if list_match and current_subsection:
            item = list_match.group(1).strip()
            # 过滤掉 "None" 占位符（生成器在列表为空时使用），不区分大小写
            if item.lower() == 'none':
                continue
            if current_subsection == 'cognitive':
                cognitive_warnings.append(item)
            elif current_subsection == 'debt':
                technical_debt.append(item)
            elif current_subsection == 'pending':
                pending_decisions.append(item)
    
    return RisksAndDebt(
        cognitive_warnings=cognitive_warnings,
        technical_debt=technical_debt,
        pending_decisions=pending_decisions
    ), []


def _parse_semantic_anchors(content: str) -> Tuple[List[SemanticAnchor], List[ParseError]]:
    """Parse Semantic Anchors section"""
    anchors = []
    errors = []
    
    # Match format: [Module] `path` -> `Symbol` or [Module] path -> Symbol
    anchor_pattern = r'\[([^\]]+)\]\s*`?([^`\s]+)`?\s*->\s*`?([^`\s]+)`?'
    
    for line in content.split('\n'):
        if line.strip().startswith('-') or line.strip().startswith('*'):
            match = re.search(anchor_pattern, line)
            if match:
                anchors.append(SemanticAnchor(
                    module=match.group(1).strip(),
                    path=match.group(2).strip(),
                    symbol=match.group(3).strip()
                ))
    
    return anchors, errors


def parse_pulse(content: str) -> ParseResult:
    """
    Parse PULSE document
    
    Args:
        content: Markdown content of PULSE document
        
    Returns:
        ParseResult: Contains parse result or error information
    """
    errors = []
    
    # Find all sections
    sections = _find_sections(content)
    
    # Validate presence of four required sections
    for section_name in REQUIRED_SECTIONS:
        if section_name not in sections:
            readable_name = section_name.replace('_', ' ').title()
            errors.append(ParseError(readable_name, f'Missing required section: {readable_name}'))
    
    if errors:
        return ParseResult(valid=False, errors=errors)
    
    # Parse each section
    mental_model, mm_errors = _parse_mental_model(sections['mental_model'])
    errors.extend(mm_errors)
    
    narrative_delta, nd_errors = _parse_narrative_delta(sections['narrative_delta'])
    errors.extend(nd_errors)
    
    risks_and_debt, rd_errors = _parse_risks_and_debt(sections['risks_and_debt'])
    errors.extend(rd_errors)
    
    semantic_anchors, sa_errors = _parse_semantic_anchors(sections['semantic_anchors'])
    errors.extend(sa_errors)
    
    if errors:
        return ParseResult(valid=False, errors=errors)
    
    return ParseResult(
        valid=True,
        document=PulseDocument(
            mental_model=mental_model,
            narrative_delta=narrative_delta,
            risks_and_debt=risks_and_debt,
            semantic_anchors=semantic_anchors
        )
    )


def generate_pulse(document: PulseDocument) -> str:
    """
    Generate PULSE document from structured data
    
    Args:
        document: PulseDocument structured data
        
    Returns:
        str: Generated Markdown content
    """
    lines = ['# PROJECT_PULSE', '']
    
    # Mental Model
    lines.append('## 🟢 Mental Model')
    lines.append('')
    lines.append(document.mental_model.description)
    lines.append('')
    lines.append('```mermaid')
    lines.append(document.mental_model.mermaid_diagram)
    lines.append('```')
    lines.append('')
    
    # Narrative Delta
    lines.append('## 🟡 Narrative Delta')
    lines.append('')
    if document.narrative_delta:
        lines.append(document.narrative_delta)
    lines.append('')
    
    # Risks & Debt section
    lines.append('## 🔴 Risks & Debt')
    lines.append('')
    
    lines.append('### Cognitive Load Warnings')
    if document.risks_and_debt.cognitive_warnings:
        for warning in document.risks_and_debt.cognitive_warnings:
            lines.append(f'- {warning}')
    else:
        lines.append('- None')
    lines.append('')
    
    lines.append('### Technical Debt')
    if document.risks_and_debt.technical_debt:
        for debt in document.risks_and_debt.technical_debt:
            lines.append(f'- {debt}')
    else:
        lines.append('- None')
    lines.append('')
    
    lines.append('### Pending Decisions')
    if document.risks_and_debt.pending_decisions:
        for decision in document.risks_and_debt.pending_decisions:
            lines.append(f'- {decision}')
    else:
        lines.append('- None')
    lines.append('')
    
    # Semantic Anchors 节
    lines.append('## 🔗 Semantic Anchors')
    lines.append('')
    if document.semantic_anchors:
        for anchor in document.semantic_anchors:
            lines.append(f'- [{anchor.module}] `{anchor.path}` -> `{anchor.symbol}`')
    else:
        lines.append('- None')
    
    return '\n'.join(lines)


def documents_semantically_equal(doc1: PulseDocument, doc2: PulseDocument) -> bool:
    """
    Compare whether two PULSE documents are semantically equivalent
    
    Args:
        doc1: First document
        doc2: Second document
        
    Returns:
        bool: Whether semantically equivalent
    """
    # Helper function: normalize string (convert all whitespace to regular spaces and strip)
    def normalize_text(text: str) -> str:
        # Convert all whitespace (including \xa0 non-breaking space) to regular spaces
        import re
        return re.sub(r'\s+', ' ', text).strip()
    
    # Compare Mental Model
    if normalize_text(doc1.mental_model.description) != normalize_text(doc2.mental_model.description):
        return False
    if doc1.mental_model.mermaid_diagram.strip() != doc2.mental_model.mermaid_diagram.strip():
        return False
    
    # Compare Narrative Delta (ignore whitespace differences)
    if normalize_text(doc1.narrative_delta) != normalize_text(doc2.narrative_delta):
        return False
    
    # Compare Risks & Debt (normalize each item)
    def normalize_list(items: List[str]) -> set:
        return {normalize_text(item) for item in items}
    
    if normalize_list(doc1.risks_and_debt.cognitive_warnings) != normalize_list(doc2.risks_and_debt.cognitive_warnings):
        return False
    if normalize_list(doc1.risks_and_debt.technical_debt) != normalize_list(doc2.risks_and_debt.technical_debt):
        return False
    if normalize_list(doc1.risks_and_debt.pending_decisions) != normalize_list(doc2.risks_and_debt.pending_decisions):
        return False
    
    # Compare Semantic Anchors
    anchors1 = {(a.module, a.path, a.symbol) for a in doc1.semantic_anchors}
    anchors2 = {(a.module, a.path, a.symbol) for a in doc2.semantic_anchors}
    if anchors1 != anchors2:
        return False
    
    return True


if __name__ == '__main__':
    # Simple test
    import sys
    
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            content = f.read()
        
        result = parse_pulse(content)
        if result.valid:
            print('✅ Document is valid')
            print(f'  Mental Model: {result.document.mental_model.description[:50]}...')
            print(f'  Anchors: {len(result.document.semantic_anchors)}')
        else:
            print('❌ Document has errors:')
            for error in result.errors:
                print(f'  [{error.section}] {error.message}')
