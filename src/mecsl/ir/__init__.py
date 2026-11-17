"""Intermediate representation package."""

from mecsl.ir.instruction import Instruction, Opcode, LinkedModule
from mecsl.ir.generator import IRGenerator

__all__ = ["Instruction", "Opcode", "LinkedModule", "IRGenerator"]
