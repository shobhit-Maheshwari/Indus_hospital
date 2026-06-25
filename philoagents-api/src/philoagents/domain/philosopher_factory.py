from philoagents.domain.philosopher import Philosopher

class PhilosopherFactory:
    @staticmethod
    def get_philosopher(id: str) -> Philosopher:
        return Philosopher(
            id="aura",
            name="Aura",
            perspective="You are Aura, the official AI medical assistant for Indus Hospital.",
            style="Professional and helpful",
            era="Modern"
        )

    @staticmethod
    def get_available_philosophers() -> list[str]:
        return ["aura"]
