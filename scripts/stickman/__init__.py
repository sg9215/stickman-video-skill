"""stickman — a professional stickman video engine.

Reverse-engineered from StykAnimate's native model (segment trees, absolute
pose angles, keyframe easing, camera semantics) with a planning methodology
adapted from stickman-video-director.
"""
__version__ = "1.0.0"

from . import actions, animation, camera, environment, easing, plan, poses, renderer, rig, styk_export, textover, video  # noqa: F401
