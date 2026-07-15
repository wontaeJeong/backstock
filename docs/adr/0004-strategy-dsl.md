# ADR-0004: JSON AST 전략 DSL

- Status: Accepted
- Date: 2026-07-16

## Context
사용자 Python 실행은 보안, 재현성, validation, UI 편집에 위험하다.

## Decision
allowlist 기반 JSON AST를 사용하고 indicator, comparison, sizing, risk, order rule을 schema로 검증한다.

## Consequences
안전하고 버전 관리가 쉽지만 표현 범위는 제한된다.
