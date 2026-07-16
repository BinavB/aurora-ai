# ARCHITECTURE.md

# AEGIS AI Engineering Platform

Version: 1.0

---

# Vision

AEGIS is a modular AI Software Engineering Platform capable of understanding, planning, writing, reviewing, testing, and maintaining software projects.

The system must support both local and cloud LLMs while remaining provider-independent.

The architecture prioritizes:

* Maintainability
* Scalability
* Extensibility
* Reliability
* Testability
* Security
* Performance

This project is intended to become a production-quality alternative to AI coding platforms such as Cursor, Claude Code, OpenHands, Continue, Cline, and similar systems.

---

# Core Principles

Every module must have one responsibility.

No circular imports.

No duplicated logic.

No business logic inside API routes.

No provider-specific code outside providers.

No direct filesystem access outside filesystem tools.

No direct terminal execution outside terminal tools.

No direct Git access outside Git tools.

All communication occurs through interfaces.

Everything should be replaceable without affecting the rest of the application.

---

# Engineering Standards

Python 3.12+

Strict typing

PEP8

Black

Ruff

Pytest

Async where beneficial

Dependency Injection

SOLID

Clean Architecture

Repository Pattern where appropriate

Google-style docstrings

Small focused modules

Readable code over clever code.

---

# Project Structure

```text
aegis/

├── app/
│   ├── api/
│   ├── agents/
│   ├── providers/
│   ├── tools/
│   ├── memory/
│   ├── router/
│   ├── planner/
│   ├── reviewer/
│   ├── context/
│   ├── terminal/
│   ├── filesystem/
│   ├── git/
│   ├── config/
│   ├── database/
│   ├── events/
│   ├── core/
│   └── services/
│
├── tests/
│
├── docs/
│
├── scripts/
│
├── plugins/
│
├── frontend/
│
└── pyproject.toml
```

---

# Layer Responsibilities

## Core

Shared utilities.

Configuration

Logging

Exceptions

Constants

Dependency Injection

Events

Utilities

No business logic.

---

## Providers

Responsible for LLM communication only.

Supported providers

* Ollama
* OpenAI
* Anthropic
* Gemini
* xAI
* Future providers

All providers inherit from:

BaseProvider

No provider should know about another provider.

---

## Agents

Planner

Coder

Reviewer

Executor

Memory

Conversation

Context Builder

Router

Each agent performs one task only.

Agents never call external APIs directly.

Agents only communicate through interfaces.

---

# Router

The Router decides

Which provider

Which model

Which tools

Which context

Routing decisions should consider

Model capability

Latency

Availability

Cost

Offline mode

User preference

---

# Tool System

Everything external is a Tool.

Examples

ReadFile

WriteFile

DeleteFile

RenameFile

SearchProject

RunTerminal

RunTests

GitStatus

GitCommit

GitDiff

Docker

Python

Formatter

Linter

Each tool exposes

Input schema

Output schema

Metadata

Validation

Permission requirements

Tools return structured data only.

Never raw console output.

---

# Filesystem Rules

Only Filesystem Tools may access files.

Atomic writes.

Create backups before overwriting.

Normalize paths.

Prevent directory traversal.

Cross-platform support.

---

# Terminal Rules

Only Terminal Tools execute commands.

Capture

stdout

stderr

exit code

execution time

Support streaming.

Never execute dangerous commands without confirmation.

---

# Git Rules

Git operations only through Git Tools.

Never auto commit.

Never auto push.

Require explicit approval.

---

# Context Engine

Never load entire repositories.

Pipeline

Understand request

Locate relevant files

Extract symbols

Compress context

Build prompt

Token efficiency is mandatory.

---

# Memory

Store

Conversation history

Architecture decisions

Project metadata

Coding style

Previous fixes

Known issues

User preferences

Current milestone

SQLite first.

Vector database later.

Memory implementation must be provider-independent.

---

# API Layer

FastAPI

REST

Streaming

WebSockets

No business logic.

Only orchestration.

---

# Services

Services coordinate business logic.

API calls Services.

Services call Agents.

Agents call Tools.

Tools access the system.

---

# Error Handling

Never ignore exceptions.

Return structured errors.

Log all unexpected failures.

No silent failures.

---

# Logging

Centralized.

Structured logging.

Levels

DEBUG

INFO

WARNING

ERROR

CRITICAL

Never log

API keys

Passwords

Secrets

Personal information

---

# Testing

Every public module must include tests.

Unit tests

Integration tests

System tests

No feature is complete without tests.

---

# Dependency Rules

Allowed

API

↓

Services

↓

Agents

↓

Tools

↓

Providers

Forbidden

Provider calling Agent

Tool calling API

Agent calling FastAPI

Filesystem access outside Tools

Terminal access outside Tools

Git access outside Git Tools

---

# Security

Validate every input.

Validate every path.

Validate every command.

No shell injection.

No path traversal.

No secret leakage.

No unsafe deserialization.

---

# Plugin System

Future plugins should be loadable without modifying existing modules.

Every plugin exposes

Metadata

Capabilities

Dependencies

Configuration

Lifecycle hooks

---

# Coding Rules

Never generate placeholder implementations.

Never generate TODO code.

Always return production-ready code.

Keep functions under approximately 50 lines when practical.

Prefer composition over inheritance.

Prefer interfaces over concrete implementations.

Avoid global state.

---

# AI Behaviour

When implementing features

Understand existing architecture first.

Never rewrite unrelated modules.

Never introduce breaking changes.

Always preserve compatibility.

Prefer incremental changes.

If requirements are ambiguous

Ask before implementing.

---

# Development Workflow

Every feature follows

Plan

Implement

Test

Review

Refactor

Document

Wait for approval

No milestone proceeds until the previous milestone is accepted.

---

# Milestone Policy

The AI must implement one milestone at a time.

Never generate the entire project.

Each milestone must compile successfully.

Each milestone must include tests.

Each milestone must preserve compatibility.

Stop after completing the requested milestone.

Wait for confirmation.

---

# Definition of Done

A task is complete only when

✓ Code compiles

✓ Tests pass

✓ Documentation updated

✓ Logging added

✓ Error handling included

✓ Type hints complete

✓ Lint passes

✓ Architecture preserved

Otherwise the task is incomplete.

---

End of Architecture Specification.
