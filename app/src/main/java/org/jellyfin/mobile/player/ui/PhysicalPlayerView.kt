package org.jellyfin.mobile.player.ui

import android.content.Context
import android.util.AttributeSet
import android.view.KeyEvent
import android.view.View
import android.view.ViewGroup
import android.widget.ImageButton
import androidx.media3.ui.DefaultTimeBar
import androidx.media3.ui.PlayerView
import org.jellyfin.mobile.BuildConfig
import org.jellyfin.mobile.R

/** Mobile Media3 controller, with remote wake/focus and ordinary Android focus navigation. */
class PhysicalPlayerView @JvmOverloads constructor(context: Context, attrs: AttributeSet? = null) : PlayerView(context, attrs) {
    private var wakeKey: Int? = null

    override fun onFinishInflate() {
        super.onFinishInflate()
        if (!BuildConfig.PHYSICAL_NAVIGATION) return
        fun decorate(view: View) {
            if (view is ImageButton) {
                view.isFocusable = true
                view.setBackgroundResource(R.drawable.physical_player_focus)
            }
            if (view is ViewGroup) for (index in 0 until view.childCount) decorate(view.getChildAt(index))
        }
        decorate(this)
        findViewById<DefaultTimeBar>(R.id.exo_progress)?.apply {
            isFocusable = true
            setKeyTimeIncrement(10_000)
        }
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (!BuildConfig.PHYSICAL_NAVIGATION || !useController || event.hasModifiers()) return super.dispatchKeyEvent(event)
        val navigation = event.keyCode in intArrayOf(
            KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_DPAD_DOWN, KeyEvent.KEYCODE_DPAD_LEFT,
            KeyEvent.KEYCODE_DPAD_RIGHT, KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_NUMPAD_ENTER,
        )
        if (!navigation) return super.dispatchKeyEvent(event) // MediaSession remains responsible for media keys.
        if (wakeKey == event.keyCode) {
            if (event.action == KeyEvent.ACTION_UP) wakeKey = null
            return true
        }
        if (event.action == KeyEvent.ACTION_DOWN) {
            if (!isControllerFullyVisible) {
                wakeKey = event.keyCode
                showController()
                findViewById<View>(R.id.exo_play_pause)?.requestFocus()
                return true
            }
            showController() // Refresh the timeout for each physical interaction, including seek repeats.
            if (event.repeatCount > 0 && event.keyCode in intArrayOf(
                    KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_NUMPAD_ENTER,
                )
            ) return true
        }
        return super.dispatchKeyEvent(event)
    }
}

private fun KeyEvent.hasModifiers() = isAltPressed || isCtrlPressed || isMetaPressed || isShiftPressed
