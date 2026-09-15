"""Full V2.1 feature composition; no candidate-only file handling bypasses."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tkinter as tk
import traceback

from .foundation.config import BuildInfo

INTEGRATED_FEATURES = ('common-foundation', 'ears', 'paws', 'groom', 'hunger',
                       'drag-expectation', 'feed')


def validate_integrated_build(info):
    missing = set(INTEGRATED_FEATURES) - set(info.feature_config.enabled_features)
    if missing:
        raise ValueError('Integrated build is missing feature flags: ' + ', '.join(sorted(missing)))


def main():
    # Local imports keep metadata validation usable without a Windows UI.
    from .assets import (load_frames, load_feed_frames, load_groom_frames,
                         load_head_neck_compositor, load_playback_sequences,
                         load_paw_compositor, load_paw_motion_config)
    from .expectation_assets import load_expectation_frames
    from .eye_follow import Win32CursorProvider
    from .feed_core.runtime import FeedRuntime
    from .foundation.services import create_application_services
    from .foundation_contract import SharedHungerState
    from .hunger import HungerService, OffsetUtcClock
    from .hunger_graphic_assets import load_hunger_graphic_assets
    from .hunger_graphic_runtime import HungerGraphicRuntime
    from .integrated_window import IntegratedDropService, IntegratedWindow
    from .main import (SingleInstanceMutex, build_mutex_name,
                       enable_per_monitor_dpi_awareness, notify_existing_instance,
                       show_fatal_error)
    from .win32_pointer import Win32ButtonState, Win32CursorMovementService

    enable_per_monitor_dpi_awareness()
    mutex = SingleInstanceMutex(build_mutex_name())
    services = root = pet = feed = hunger = None
    try:
        info = BuildInfo.load_embedded()
        validate_integrated_build(info)
        if not mutex.acquire():
            notify_existing_instance(info)
            return 0
        services = create_application_services(info)
        state = services.load_state()
        root = tk.Tk()
        diagnostics = os.environ.get('DESKTOP_PET_STARTUP_DIAGNOSTICS')
        if diagnostics:
            def callback_error(kind, error, trace):
                destination = Path(diagnostics)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open('a', encoding='utf-8') as stream:
                    stream.write(''.join(traceback.format_exception(kind, error, trace)))
                root.quit()
            root.report_callback_exception = callback_error
        root.withdraw()
        utc_clock = OffsetUtcClock(lambda: int(services.runtime.clock.utc_now().timestamp()))
        hunger = HungerService(SharedHungerState(services), utc_clock.utc_seconds)
        feed = FeedRuntime(services, root, hunger=hunger)
        services.dragdrop.close()
        services.dragdrop = IntegratedDropService(feed)
        compositor = load_head_neck_compositor()
        expectation_frames = load_expectation_frames(expected_size=compositor.source_size)
        pet = IntegratedWindow(
            root, load_frames(), compositor=compositor,
            cursor_provider=Win32CursorProvider(), head_follow=True,
            services=services, persisted_state=state,
            animation_sequences=load_playback_sequences(),
            cursor_service_factory=lambda _hwnd: Win32CursorMovementService(),
            button_state_factory=lambda _hwnd: Win32ButtonState(),
            paw_compositor=load_paw_compositor(), paw_motion_config=load_paw_motion_config(),
            groom_frames=load_groom_frames(),
            groom_other_frames={'right': load_groom_frames('right')},
            groom_debug_menu=info.feature_config.debug_menu_enabled,
            hunger=hunger, expectation_frames=expectation_frames, feed_runtime=feed,
        )
        feed.attach_window(pet, load_feed_frames())
        hunger_runtime = HungerGraphicRuntime(services=services, service=hunger,
                                             window=pet, clock=services.runtime.clock)
        pet.attach_hunger(hunger_runtime, load_hunger_graphic_assets(pet._neutral_center_frame), utc_clock)
        hunger_runtime.start()
        if os.environ.get('DESKTOP_PET_SMOKE_CHECK') == '1' and info.feature_config.test_build:
            def smoke_ready():
                payload = {
                    'ready': pet._window_shown,
                    'enabled_features': list(info.feature_config.enabled_features),
                    'same_runtime': pet.services is feed.services is pet.expectation.services,
                    'same_hunger': hunger is feed.hunger is pet.expectation.hunger is hunger_runtime.service,
                    'single_drop_owner': services.dragdrop.handler is pet.expectation,
                    'feed_frames': len(pet.frames['feed']),
                    'expectation_frames': len(expectation_frames),
                    'groom': pet.groom_readiness(),
                    'git_short_hash': info.git_short_hash,
                }
                with (services.paths.root/'smoke-ready.json').open('x', encoding='utf-8') as stream:
                    json.dump(payload, stream)
            root.after_idle(smoke_ready)
        root.mainloop()
        return 0
    except (OSError, RuntimeError, ValueError, TypeError, AttributeError, tk.TclError) as error:
        destination = os.environ.get('DESKTOP_PET_STARTUP_DIAGNOSTICS')
        if destination:
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(traceback.format_exc(), encoding='utf-8')
        else:
            show_fatal_error(str(error), root)
        return 1
    finally:
        try:
            if pet is not None:
                pet.close()
            else:
                try:
                    if feed is not None:
                        feed.close()
                    if hunger is not None:
                        hunger.close()
                finally:
                    if services is not None:
                        services.close()
                    if root is not None:
                        root.destroy()
        finally:
            mutex.close()


if __name__ == '__main__':
    raise SystemExit(main())
