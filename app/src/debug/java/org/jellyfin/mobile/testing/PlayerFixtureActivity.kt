package org.jellyfin.mobile.testing

import android.os.Bundle
import androidx.activity.addCallback
import androidx.appcompat.app.AppCompatActivity
import org.jellyfin.mobile.R
import org.jellyfin.mobile.player.interaction.PlayOptions
import org.jellyfin.mobile.player.ui.PlayerFragment
import org.jellyfin.mobile.utils.Constants
import org.jellyfin.mobile.utils.extensions.addFragment
import org.jellyfin.sdk.api.client.ApiClient
import org.koin.android.ext.android.get
import java.util.UUID

/** Non-exported debug host: exercises the real mobile player against a downloaded local fixture. */
class PlayerFixtureActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        get<ApiClient>().update(baseUrl = "http://127.0.0.1:9")
        setContentView(R.layout.activity_main)
        if (savedInstanceState == null) {
            val id = UUID.fromString(intent.getStringExtra("fixtureItemId"))
            supportFragmentManager.addFragment<PlayerFragment>(Bundle().apply {
                putParcelable(Constants.EXTRA_MEDIA_PLAY_OPTIONS, PlayOptions(listOf(id), id.toString(), 0, null, null, null, true))
            })
        }
        onBackPressedDispatcher.addCallback(this) {
            val fragment = supportFragmentManager.findFragmentById(R.id.fragment_container) as? PlayerFragment
            if (fragment?.onInterceptBackPressed() != true) finish()
        }
    }
}
