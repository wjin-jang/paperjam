/* PaperJam Web — Audio Player Engine */

const Player = {
    audio: new Audio(),
    queue: [],
    queueIndex: -1,
    shuffle: false,
    loop: 0, // 0=off, 1=all, 2=one
    currentTrack: null,
    quality: 'high',
    _progressInterval: null,

    init() {
        this.audio.addEventListener('ended', () => this._onEnded());
        this.audio.addEventListener('error', (e) => {
            console.error('Audio error:', e);
        });

        // Media Session API for system notifications/controls
        if ('mediaSession' in navigator) {
            navigator.mediaSession.setActionHandler('play', () => this.resume());
            navigator.mediaSession.setActionHandler('pause', () => this.pause());
            navigator.mediaSession.setActionHandler('previoustrack', () => this.prev());
            navigator.mediaSession.setActionHandler('nexttrack', () => this.next());
        }

        // Load settings
        API.settings().then(s => {
            this.quality = s.streaming_quality || 'high';
        }).catch(() => {});
    },

    play(track, trackList, startIndex) {
        if (trackList) {
            this.queue = [...trackList];
            this.queueIndex = startIndex >= 0 ? startIndex : 0;
        }
        this._loadTrack(track);
    },

    _loadTrack(track) {
        this.currentTrack = track;
        const url = API.streamUrl(track.path, this.quality);
        this.audio.src = url;
        this.audio.play().catch(() => {});

        this._updateUI();
        this._startProgress();
        this._updateMediaSession();
    },

    resume() {
        if (this.audio.src) {
            this.audio.play().catch(() => {});
            this._updatePlayButton();
        }
    },

    pause() {
        this.audio.pause();
        this._updatePlayButton();
    },

    toggle() {
        if (this.audio.paused) this.resume();
        else this.pause();
    },

    next() {
        if (this.queue.length === 0) return;

        if (this.loop === 2) {
            // Loop one: replay current
            this.audio.currentTime = 0;
            this.audio.play().catch(() => {});
            return;
        }

        let nextIdx = this.queueIndex + 1;
        if (nextIdx >= this.queue.length) {
            if (this.loop === 1) nextIdx = 0; // Loop all: wrap
            else return; // No loop: stop
        }

        this.queueIndex = nextIdx;
        this._loadTrack(this.queue[this.queueIndex]);
    },

    prev() {
        if (this.queue.length === 0) return;

        // If past 3 seconds, restart track
        if (this.audio.currentTime > 3) {
            this.audio.currentTime = 0;
            return;
        }

        let prevIdx = this.queueIndex - 1;
        if (prevIdx < 0) {
            if (this.loop === 1) prevIdx = this.queue.length - 1;
            else prevIdx = 0;
        }

        this.queueIndex = prevIdx;
        this._loadTrack(this.queue[this.queueIndex]);
    },

    seekTo(fraction) {
        if (this.audio.duration) {
            this.audio.currentTime = fraction * this.audio.duration;
        }
    },

    setVolume(val) {
        this.audio.volume = val / 100;
    },

    toggleShuffle() {
        this.shuffle = !this.shuffle;
        if (this.shuffle && this.queue.length > 1) {
            // Shuffle queue, keeping current track in place
            const current = this.queue[this.queueIndex];
            const rest = this.queue.filter((_, i) => i !== this.queueIndex);
            for (let i = rest.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [rest[i], rest[j]] = [rest[j], rest[i]];
            }
            this.queue = [current, ...rest];
            this.queueIndex = 0;
        }
        document.getElementById('btn-shuffle').classList.toggle('active', this.shuffle);
    },

    cycleLoop() {
        this.loop = (this.loop + 1) % 3;
        const btn = document.getElementById('btn-loop');
        btn.classList.toggle('active', this.loop > 0);
        const labels = ['Loop', 'Loop All', 'Loop One'];
        btn.textContent = labels[this.loop];
    },

    getQueue() {
        return this.queue.map((t, i) => ({ ...t, isCurrent: i === this.queueIndex }));
    },

    playFromQueue(index) {
        if (index >= 0 && index < this.queue.length) {
            this.queueIndex = index;
            this._loadTrack(this.queue[index]);
        }
    },

    removeFromQueue(index) {
        if (index < 0 || index >= this.queue.length) return;
        this.queue.splice(index, 1);
        if (index < this.queueIndex) this.queueIndex--;
        if (this.queueIndex >= this.queue.length) this.queueIndex = this.queue.length - 1;
    },

    addToQueue(track) {
        this.queue.push(track);
    },

    _onEnded() {
        if (this.loop === 2) {
            this.audio.currentTime = 0;
            this.audio.play().catch(() => {});
        } else {
            this.next();
        }
    },

    _updateUI() {
        const bar = document.getElementById('player-bar');
        bar.classList.remove('empty');

        const t = this.currentTrack;
        document.getElementById('player-title').textContent = t.title || 'Unknown';
        document.getElementById('player-artist').textContent = t.artist || 'Unknown';

        const cover = document.getElementById('player-cover');
        cover.src = API.coverUrl(t.path, 'small');
        cover.onerror = () => { cover.src = ''; };

        this._updatePlayButton();

        // Update fav button
        API.checkFavorite('track', t.path).then(r => {
            document.getElementById('btn-fav').textContent = r.favorited ? '♥' : '♡';
            document.getElementById('btn-fav').classList.toggle('active', r.favorited);
        }).catch(() => {});

        // Notify app of track change
        if (typeof App !== 'undefined' && App.onTrackChange) {
            App.onTrackChange(t);
        }
    },

    _updatePlayButton() {
        const btn = document.getElementById('btn-play');
        btn.textContent = this.audio.paused ? '▶' : '⏸';
    },

    _startProgress() {
        if (this._progressInterval) clearInterval(this._progressInterval);
        this._progressInterval = setInterval(() => {
            if (!this.audio.duration) return;
            const pct = (this.audio.currentTime / this.audio.duration) * 100;
            document.getElementById('progress-fill').style.width = pct + '%';
            document.getElementById('time-current').textContent = this._fmt(this.audio.currentTime);
            document.getElementById('time-total').textContent = this._fmt(this.audio.duration);
            this._updatePlayButton();
        }, 250);
    },

    _fmt(s) {
        if (!s || isNaN(s)) return '0:00';
        const m = Math.floor(s / 60);
        const sec = Math.floor(s % 60);
        return `${m}:${sec.toString().padStart(2, '0')}`;
    },

    _updateMediaSession() {
        if (!('mediaSession' in navigator) || !this.currentTrack) return;
        const t = this.currentTrack;
        navigator.mediaSession.metadata = new MediaMetadata({
            title: t.title,
            artist: t.artist,
            album: t.album,
            artwork: [
                { src: API.coverUrl(t.path, 'small'), sizes: '128x128', type: 'image/jpeg' },
                { src: API.coverUrl(t.path, 'large'), sizes: '600x600', type: 'image/jpeg' },
            ],
        });
    },
};
