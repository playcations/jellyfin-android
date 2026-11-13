package org.jellyfin.mobile

import android.content.Intent
import android.view.KeyEvent
import android.view.View
import androidx.core.net.toUri
import androidx.lifecycle.ViewModelProvider
import androidx.media3.common.Player
import androidx.media3.ui.PlayerView
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.jellyfin.mobile.data.dao.DownloadDao
import org.jellyfin.mobile.data.dao.ServerDao
import org.jellyfin.mobile.data.dao.UserDao
import org.jellyfin.mobile.data.entity.DownloadEntity
import org.jellyfin.mobile.data.entity.DownloadFileEntity
import org.jellyfin.mobile.downloads.DownloadFileType
import org.jellyfin.mobile.downloads.DownloadStatus
import org.jellyfin.mobile.player.PlayerViewModel
import org.jellyfin.mobile.player.ui.PlayerFragment
import org.jellyfin.mobile.testing.PlayerFixtureActivity
import org.jellyfin.sdk.model.api.BaseItemKind
import org.jellyfin.sdk.model.api.MediaProtocol
import org.jellyfin.sdk.model.api.MediaSourceType
import org.jellyfin.sdk.model.api.MediaStreamProtocol
import org.jellyfin.sdk.model.api.BaseItemDto
import org.jellyfin.sdk.model.api.MediaSourceInfo
import org.jellyfin.sdk.model.api.MediaStream
import org.jellyfin.sdk.model.api.MediaStreamType
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.koin.core.context.GlobalContext
import java.io.File
import java.util.UUID

class PhysicalPlayerTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()

    @Test
    fun realMobilePlayerSupportsRemoteMenusSeekWakeAndTimeout() {
        assumeTrue(BuildConfig.PHYSICAL_NAVIGATION)
        val context = instrumentation.targetContext
        val fixture = File(context.cacheDir, "familyfin-player-fixture.mp4")
        instrumentation.context.assets.open("player-fixture.mp4").use { input -> fixture.outputStream().use(input::copyTo) }
        val koin = GlobalContext.get()
        val server = koin.get<ServerDao>().insert("http://127.0.0.1:9/fixture-${UUID.randomUUID()}")
        val user = koin.get<UserDao>().insert(server, UUID.randomUUID(), null)
        val itemId = UUID.randomUUID()
        val streams = listOf(
            MediaStream(isInterlaced = false, isDefault = false, isForced = false, isHearingImpaired = false, isExternal = false, isTextSubtitleStream = false, supportsExternalStream = false, index = 0, type = MediaStreamType.VIDEO, codec = "h264", width = 320, height = 180),
            MediaStream(isInterlaced = false, isDefault = false, isForced = false, isHearingImpaired = false, isExternal = false, isTextSubtitleStream = false, supportsExternalStream = false, index = 1, type = MediaStreamType.AUDIO, codec = "aac", displayTitle = "English fixture", language = "eng"),
            MediaStream(isInterlaced = false, isDefault = false, isForced = false, isHearingImpaired = false, isExternal = false, isTextSubtitleStream = false, supportsExternalStream = false, index = 2, type = MediaStreamType.AUDIO, codec = "aac", displayTitle = "French fixture", language = "fra"),
            MediaStream(isInterlaced = false, isDefault = false, isForced = false, isHearingImpaired = false, isExternal = false, isTextSubtitleStream = false, supportsExternalStream = false, index = 3, type = MediaStreamType.SUBTITLE, codec = "mov_text", displayTitle = "English subtitles", language = "eng"),
            MediaStream(isInterlaced = false, isDefault = false, isForced = false, isHearingImpaired = false, isExternal = false, isTextSubtitleStream = false, supportsExternalStream = false, index = 4, type = MediaStreamType.SUBTITLE, codec = "mov_text", displayTitle = "French subtitles", language = "fra"),
        )
        val source = MediaSourceInfo(protocol = MediaProtocol.FILE, type = MediaSourceType.DEFAULT, isRemote = false, readAtNativeFramerate = false,
            ignoreDts = false, ignoreIndex = false, genPtsInput = false, supportsTranscoding = false,
            supportsDirectStream = true, supportsDirectPlay = true, isInfiniteStream = false,
            requiresOpening = false, requiresClosing = false, requiresLooping = false, supportsProbing = false,
            transcodingSubProtocol = MediaStreamProtocol.HTTP, hasSegments = false, id = itemId.toString(), container = "mp4", runTimeTicks = 1_200_000_000,
            mediaStreams = streams, defaultAudioStreamIndex = 1)
        val dao = koin.get<DownloadDao>()
        val download = runBlocking {
            val id = dao.insert(DownloadEntity(serverId = server, userId = user, itemId = itemId, path = fixture.path,
                item = BaseItemDto(type = BaseItemKind.MOVIE, id = itemId, name = "Local player fixture", mediaSources = listOf(source), runTimeTicks = 1_200_000_000),
                status = DownloadStatus.DOWNLOADED))
            dao.insertFile(DownloadFileEntity(downloadId = id, type = DownloadFileType.ITEM, size = fixture.length(),
                fileName = fixture.name, uri = fixture.toUri(), status = DownloadStatus.DOWNLOADED))
            id
        }
        try {
            ActivityScenario.launch<PlayerFixtureActivity>(Intent(context, PlayerFixtureActivity::class.java)
                .putExtra("fixtureItemId", itemId.toString())).use { scenario ->
                fun onPlayer(block: (PlayerFixtureActivity, PlayerFragment, PlayerView, PlayerViewModel) -> Unit) {
                    scenario.onActivity { activity ->
                        val fragment = activity.supportFragmentManager.findFragmentById(R.id.fragment_container) as PlayerFragment
                        block(activity, fragment, activity.findViewById(R.id.player_view), ViewModelProvider(fragment)[PlayerViewModel::class.java])
                    }
                }
                fun awaitState(message: String, timeout: Long = 30_000, predicate: (PlayerViewModel) -> Boolean) {
                    val end = System.currentTimeMillis() + timeout
                    while (System.currentTimeMillis() < end) {
                        var ready = false
                        onPlayer { _, _, _, model -> ready = predicate(model) }
                        if (ready) return
                        Thread.sleep(200)
                    }
                    fail(message)
                }
                fun key(code: Int) { instrumentation.sendKeyDownUpSync(code); instrumentation.waitForIdleSync() }
                fun focus(id: Int) { onPlayer { activity, _, view, _ -> view.showController();assertTrue(activity.findViewById<View>(id).requestFocus()) } }
                awaitState("Fixture must actually decode and play", 120_000) { it.playerOrNull?.playbackState == Player.STATE_READY && it.playerOrNull!!.currentPosition > 500 }
                onPlayer { _, _, view, model ->
                    model.playerOrNull!!.pause()
                    view.hideController()
                }
                key(KeyEvent.KEYCODE_DPAD_CENTER)
                onPlayer { activity, _, view, model ->
                    assertTrue(view.isControllerFullyVisible)
                    assertEquals(R.id.exo_play_pause, activity.currentFocus?.id)
                    assertFalse("Wake must not toggle playback", model.playerOrNull!!.playWhenReady)
                }
                // A one-item queue disables Next; traverse toward the enabled Previous control.
                key(KeyEvent.KEYCODE_DPAD_LEFT)
                onPlayer { activity, _, _, _ -> assertEquals(R.id.previous_button, activity.currentFocus?.id) }
                focus(R.id.exo_progress)
                key(KeyEvent.KEYCODE_DPAD_RIGHT); key(KeyEvent.KEYCODE_DPAD_CENTER)
                onPlayer { _, _, _, model -> assertTrue("Timebar seeks by remote", model.playerOrNull!!.currentPosition >= 9_000) }
                focus(R.id.audio_streams_button); key(KeyEvent.KEYCODE_DPAD_CENTER)
                key(KeyEvent.KEYCODE_DPAD_DOWN); key(KeyEvent.KEYCODE_DPAD_DOWN); key(KeyEvent.KEYCODE_DPAD_CENTER)
                awaitState("Remote audio menu selects French") { it.mediaSourceOrNull?.selectedAudioStreamIndex == 2 }
                onPlayer { activity, _, view, _ ->
                    assertEquals(R.id.audio_streams_button, activity.currentFocus?.id)
                    assertTrue(view.controllerShowTimeoutMs > 0)
                }
                focus(R.id.subtitles_button);key(KeyEvent.KEYCODE_DPAD_CENTER)
                key(KeyEvent.KEYCODE_DPAD_DOWN);key(KeyEvent.KEYCODE_DPAD_DOWN);key(KeyEvent.KEYCODE_DPAD_CENTER)
                awaitState("Remote subtitle menu selects English") { it.mediaSourceOrNull?.selectedSubtitleStreamIndex == 3 }
                onPlayer { activity, _, _, _ -> assertEquals(R.id.subtitles_button, activity.currentFocus?.id) }
                focus(R.id.audio_streams_button);key(KeyEvent.KEYCODE_DPAD_CENTER); key(KeyEvent.KEYCODE_BACK)
                onPlayer { activity, _, view, _ -> assertEquals(R.id.audio_streams_button, activity.currentFocus?.id); assertTrue(view.isControllerFullyVisible) }
                onPlayer { _, fragment, view, model ->
                    model.playerOrNull!!.play()
                    fragment.onUserLeaveHint()
                    assertFalse("TV does not auto-enter PiP", fragment.requireActivity().isInPictureInPictureMode)
                    view.controllerShowTimeoutMs = 600
                    view.showController()
                }
                Thread.sleep(1_200)
                onPlayer { _, _, view, _ -> assertFalse("Controls auto-hide after interaction", view.isControllerFullyVisible) }
                key(KeyEvent.KEYCODE_DPAD_UP)
                onPlayer { _, _, view, model -> assertTrue(view.isControllerFullyVisible); model.mediaSession.controller.transportControls.pause() }
                awaitState("Media-session pause retained") { it.playerOrNull?.playWhenReady == false }
                onPlayer { _, fragment, _, _ -> fragment.playerLockScreenHelper.lockScreen() }
                key(KeyEvent.KEYCODE_BACK)
                onPlayer { _, _, view, _ -> assertTrue("Back unlocks controller", view.useController) }
            }
        } finally {
            runBlocking { dao.delete(download) }
            fixture.delete()
        }
    }
}
