import { PhysicalInputAdapter } from './PhysicalInputAdapter.js';

export class NavigationPlugin {
    constructor({ playbackManager, inputManager }) {
        window.NavigationHelper?.inputAdapter?.destroy();
        window.NavigationHelper = this;
        this.playbackManager = playbackManager;
        this.inputManager = inputManager;
        if (window.NativeShell?.capabilities?.physicalNavigation === true && inputManager) {
            this.inputAdapter = new PhysicalInputAdapter(inputManager);
        }
    }

    goBack() {
        // inputManager gives the active dialog/player the first chance to consume Back.
        if (this.inputAdapter) {
            this.inputAdapter.back();
        } else if (this.inputManager) {
            this.inputManager.handleCommand('back');
        } else {
            const appRouter = window.Emby.Page;
            if (appRouter.canGoBack()) appRouter.back();
            else window.NativeInterface.exitApp();
        }
    }
}
