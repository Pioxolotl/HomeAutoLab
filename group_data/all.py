"""
Dane wspólne dla wszystkich hostów. Każda zmienna (bez __) trafia do host.data.

Sekrety: nie deszyfruj ich tutaj globalnie - wtedy każde uruchomienie pyinfra,
nawet debug-inventory, wymagałoby klucza age. Deszyfruj w deploy.py usługi,
która ich potrzebuje (robi to deploys/compose_stacks.py per stack).
"""

timezone = "Europe/Warsaw"
admin_email = "ty@example.com"
