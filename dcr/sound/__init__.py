"""Stage E6 demo — offline impact-sound render of the bounded contact excitation.

Scope (CLAUDE.md, scope change 2026-07-11): this package RENDERS the per-substep
native-contact excitation logged from the solver through a band-split audio-rate
modal IIR bank (van den Doel & Pai 1998), capped by the same §15-form energy
ledger the sim path enforces. It is a demo of the E6 sound-energy bound, NOT a
claimed contribution, and it never touches the co-solved sim-rate modal band.

Import layering: everything here is importable without warp; only
`logger.attach_sound_logger` touches the live solver (imports lazily).
"""
from .audio_basis import (
    AudioBasis,
    build_box_audio_basis,
    build_shell_audio_basis,
    build_table_audio_basis,
    load_audio_basis,
    phi_at_xz,
    save_audio_basis,
    split_degenerate_pairs,
)
from .bank import render_modes_lfilter, render_modes_reference, resonator_coeffs
from .events import (
    ImpulseEvents,
    SoundLog,
    extract_impulses,
    filter_settle,
    settle_arm_index,
)
from .render import AudioLedger, Voice, render_soundtrack, write_wav
from .shaping import (
    contact_noise_burst,
    half_sine_spectrum,
    hertz_tau,
    impulse_kernel,
)

__all__ = [
    "AudioBasis",
    "AudioLedger",
    "ImpulseEvents",
    "SoundLog",
    "Voice",
    "build_box_audio_basis",
    "build_shell_audio_basis",
    "build_table_audio_basis",
    "contact_noise_burst",
    "extract_impulses",
    "filter_settle",
    "half_sine_spectrum",
    "hertz_tau",
    "settle_arm_index",
    "impulse_kernel",
    "load_audio_basis",
    "phi_at_xz",
    "render_modes_lfilter",
    "render_modes_reference",
    "render_soundtrack",
    "resonator_coeffs",
    "save_audio_basis",
    "split_degenerate_pairs",
    "write_wav",
]
