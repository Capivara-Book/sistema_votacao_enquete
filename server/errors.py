"""Exceções de domínio. Cada uma carrega o status HTTP correspondente."""


class DomainError(Exception):
    status = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(DomainError):
    """Dados malformados ou inválidos (título, opções, usuário...)."""
    status = 400


class PollNotFound(DomainError):
    status = 404

    def __init__(self, poll_id: int):
        super().__init__(f"Enquete {poll_id} não encontrada")


class Conflict(DomainError):
    """Conflito de estado: enquete encerrada ou voto duplicado."""
    status = 409


class InvalidVote(DomainError):
    """Voto que viola a regra de escolha do tipo da enquete."""
    status = 422
