"""
Core domain types shared across every other ContextShift subpackage.

Holds the framework-agnostic representations that strategies, tokenizers,
and providers all operate on -- a plain Message type and token-budget
configuration -- with no persistence or web-framework dependencies of any
kind. Every other subpackage in contextshift/ may depend on core/; core/
depends on nothing else in this package.
"""
