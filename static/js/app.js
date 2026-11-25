// YouTube to MP3 Converter Frontend Logic

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const dropZone = document.getElementById('dropZone');
  const urlInput = document.getElementById('urlInput');
  const clearBtn = document.getElementById('clearBtn');
  const pasteBtn = document.getElementById('pasteBtn');
  const fetchBtn = document.getElementById('fetchBtn');
  
  const previewCard = document.getElementById('previewCard');
  const previewThumb = document.getElementById('previewThumb');
  const previewDuration = document.getElementById('previewDuration');
  const platformBadge = document.getElementById('platformBadge');
  const editTitle = document.getElementById('editTitle');
  const editArtist = document.getElementById('editArtist');
  const qualitySelect = document.getElementById('qualitySelect');
  const qualityLabel = document.getElementById('qualityLabel');
  const embedCoverCheck = document.getElementById('embedCoverCheck');
  const embedCoverGroup = document.getElementById('embedCoverGroup');
  const convertBtn = document.getElementById('convertBtn');
  const convertBtnText = document.getElementById('convertBtnText');
  const convertBtnIcon = document.getElementById('convertBtnIcon');
  const formatMp3Btn = document.getElementById('formatMp3Btn');
  const formatMp4Btn = document.getElementById('formatMp4Btn');
  
  const trimToggle = document.getElementById('trimToggle');
  const trimContent = document.getElementById('trimContent');
  const trimArrow = document.getElementById('trimArrow');
  const trimStart = document.getElementById('trimStart');
  const trimEnd = document.getElementById('trimEnd');

  const progressCard = document.getElementById('progressCard');
  const progressPct = document.getElementById('progressPct');
  const progressBar = document.getElementById('progressBar');
  const progressStatus = document.getElementById('progressStatus');

  const resultCard = document.getElementById('resultCard');
  const resultThumb = document.getElementById('resultThumb');
  const resultTitle = document.getElementById('resultTitle');
  const resultArtist = document.getElementById('resultArtist');
  const resultBitrate = document.getElementById('resultBitrate');
  const resultSize = document.getElementById('resultSize');
  const resultDuration = document.getElementById('resultDuration');
  const downloadBtn = document.getElementById('downloadBtn');
  const downloadBtnText = document.getElementById('downloadBtnText');
  const copyLinkBtn = document.getElementById('copyLinkBtn');
  const convertAnotherBtn = document.getElementById('convertAnotherBtn');

  // Video & Audio Player Elements
  const resultVideo = document.getElementById('resultVideo');
  const audioPlayerBox = document.getElementById('audioPlayerBox');
  const nativeAudio = document.getElementById('nativeAudio');
  const playerPlayBtn = document.getElementById('playerPlayBtn');
  const playIcon = document.getElementById('playIcon');
  const pauseIcon = document.getElementById('pauseIcon');
  const audioSeeker = document.getElementById('audioSeeker');
  const audioCurrentTime = document.getElementById('audioCurrentTime');
  const audioTotalTime = document.getElementById('audioTotalTime');

  // History & Toasts
  const historyList = document.getElementById('historyList');
  const clearHistoryBtn = document.getElementById('clearHistoryBtn');
  const toastContainer = document.getElementById('toastContainer');

  let currentVideoData = null;
  let activePollInterval = null;
  let activeJobId = null;
  let selectedFormat = 'mp3';

  // --- Format Selection Logic ---
  function setFormat(fmt) {
    selectedFormat = fmt;
    if (fmt === 'mp4') {
      if (formatMp4Btn) formatMp4Btn.classList.add('active');
      if (formatMp3Btn) formatMp3Btn.classList.remove('active');
      if (convertBtnText) convertBtnText.textContent = 'Convert to MP4 Video';
      if (convertBtnIcon) {
        convertBtnIcon.innerHTML = `<polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>`;
      }
      if (qualityLabel) qualityLabel.textContent = 'Video Quality / Resolution';
      if (embedCoverGroup) embedCoverGroup.style.display = 'none';
      if (qualitySelect) {
        qualitySelect.innerHTML = `
          <option value="720" selected>720p HD (High Definition • Recommended)</option>
          <option value="1080">1080p Full HD (Best Available)</option>
          <option value="480">480p SD (Standard Resolution)</option>
        `;
      }
    } else {
      if (formatMp3Btn) formatMp3Btn.classList.add('active');
      if (formatMp4Btn) formatMp4Btn.classList.remove('active');
      if (convertBtnText) convertBtnText.textContent = 'Convert to MP3';
      if (convertBtnIcon) {
        convertBtnIcon.innerHTML = `<path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle>`;
      }
      if (qualityLabel) qualityLabel.textContent = 'Audio Bitrate / Quality';
      if (embedCoverGroup) embedCoverGroup.style.display = 'flex';
      if (qualitySelect) {
        qualitySelect.innerHTML = `
          <option value="320" selected>320 kbps (Studio Quality • Recommended)</option>
          <option value="256">256 kbps (High Fidelity)</option>
          <option value="192">192 kbps (Standard MP3)</option>
          <option value="128">128 kbps (Compact Size)</option>
        `;
      }
    }
  }

  if (formatMp3Btn) formatMp3Btn.addEventListener('click', () => setFormat('mp3'));
  if (formatMp4Btn) formatMp4Btn.addEventListener('click', () => setFormat('mp4'));

  // --- Utility Functions ---

  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let iconSvg = '';
    if (type === 'error') {
      iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    } else if (type === 'success') {
      iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    } else {
      iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }

    toast.innerHTML = `${iconSvg}<span>${escapeHtml(message)}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(20px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, m => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    })[m]);
  }

  function formatTime(seconds) {
    if (isNaN(seconds) || seconds < 0) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  }

  function extractVideoId(url) {
    if (!url) return null;
    const regExp = /(?:https?:\/\/)?(?:www\.|m\.|music\.)?(?:youtube\.com\/(?:watch\?.*?v=|shorts\/|embed\/|live\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/i;
    const match = url.trim().match(regExp);
    return match ? match[1] : null;
  }

  function extractSpotifyId(url) {
    if (!url) return null;
    const regExp = /(?:open\.spotify\.com\/(?:intl-[a-z]{2,5}\/)?track\/|spotify:track:)([a-zA-Z0-9]{22})/i;
    const match = url.trim().match(regExp);
    return match ? match[1] : null;
  }

  function extractInstagramId(url) {
    if (!url) return null;
    const regExp = /(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:[a-zA-Z0-9_\.]+\/)?(?:reel|reels|p|tv|share\/r|share\/p)\/([a-zA-Z0-9_-]+)/i;
    const match = url.trim().match(regExp);
    return match ? match[1] : null;
  }

  function isSupportedUrl(url) {
    return !!extractVideoId(url) || !!extractSpotifyId(url) || !!extractInstagramId(url);
  }

  // --- Drag and Drop Handling ---

  ['dragenter', 'dragover'].forEach(eventName => {
    window.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.add('drag-active');
    }, false);
  });

  ['dragleave', 'dragend'].forEach(eventName => {
    window.addEventListener(eventName, (e) => {
      if (!e.relatedTarget || e.relatedTarget.nodeName === 'HTML') {
        dropZone.classList.remove('drag-active');
      }
    }, false);
  });

  window.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-active');

    let droppedText = e.dataTransfer.getData('text/uri-list') || e.dataTransfer.getData('text/plain');
    if (droppedText) {
      handleUrlInput(droppedText.trim());
    }
  }, false);

  dropZone.addEventListener('click', () => {
    urlInput.focus();
  });

  // --- Input Handling & Sample Links ---

  urlInput.addEventListener('input', () => {
    const val = urlInput.value.trim();
    clearBtn.style.display = val ? 'flex' : 'none';
    if (isSupportedUrl(val)) {
      fetchVideoInfo(val);
    }
  });

  urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const val = urlInput.value.trim();
      if (val) fetchVideoInfo(val);
    }
  });

  clearBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    urlInput.value = '';
    clearBtn.style.display = 'none';
    urlInput.focus();
  });

  pasteBtn.addEventListener('click', async (e) => {
    e.stopPropagation();
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        handleUrlInput(text.trim());
      } else {
        showToast('Clipboard is empty', 'error');
      }
    } catch (err) {
      showToast('Clipboard access denied. Please paste manually.', 'error');
      urlInput.focus();
    }
  });

  fetchBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    const val = urlInput.value.trim();
    if (val) {
      fetchVideoInfo(val);
    } else {
      showToast('Please enter or drop a YouTube, Spotify, or Instagram link', 'error');
    }
  });

  document.querySelectorAll('.sample-pill').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const sampleUrl = btn.getAttribute('data-url');
      handleUrlInput(sampleUrl);
    });
  });

  function handleUrlInput(url) {
    urlInput.value = url;
    clearBtn.style.display = 'flex';
    fetchVideoInfo(url);
  }

  // --- Trimmer Accordion ---

  trimToggle.addEventListener('click', () => {
    const isClosed = trimContent.style.display === 'none';
    trimContent.style.display = isClosed ? 'flex' : 'none';
    trimArrow.style.transform = isClosed ? 'rotate(180deg)' : 'rotate(0deg)';
  });

  // --- API: Fetch Video Info ---

  async function fetchVideoInfo(url) {
    const videoId = extractVideoId(url);
    const spotifyId = extractSpotifyId(url);
    const instagramId = extractInstagramId(url);
    if (!videoId && !spotifyId && !instagramId) {
      showToast('Please provide a valid YouTube, Spotify, or Instagram link (e.g. youtu.be, youtube.com, open.spotify.com, or instagram.com/reel/...)', 'error');
      return;
    }

    // Set loading UI with animated spinner
    fetchBtn.disabled = true;
    fetchBtn.innerHTML = `
      <svg class="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-opacity="0.25"></circle>
        <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-linecap="round"></path>
      </svg>
      <span>Fetching...</span>
    `;
    previewCard.style.display = 'none';
    progressCard.style.display = 'none';
    resultCard.style.display = 'none';
    pauseAudio();

    try {
      // 1. Try Backend API with 6-second timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 6000);

      let fetchedData = null;

      try {
        const resp = await fetch('/api/info', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url }),
          signal: controller.signal
        });
        clearTimeout(timeoutId);

        if (resp.ok) {
          const res = await resp.json();
          if (res.success && res.data) {
            fetchedData = res.data;
          }
        }
      } catch (backendErr) {
        console.warn('Backend /api/info busy or unreachable, trying direct lookup...', backendErr);
      }

      // 2. Direct browser-side fallback if backend was busy
      if (!fetchedData && spotifyId) {
        try {
          const sResp = await fetch(`https://open.spotify.com/oembed?url=https://open.spotify.com/track/${spotifyId}`);
          if (sResp.ok) {
            const sData = await sResp.json();
            fetchedData = {
              id: spotifyId,
              platform: 'spotify',
              url: `https://open.spotify.com/track/${spotifyId}`,
              title: sData.title || 'Spotify Track',
              author: 'Spotify Artist',
              duration: null,
              duration_formatted: 'Ready to convert',
              thumbnail: sData.thumbnail_url || '',
              view_count: 0
            };
          }
        } catch (sErr) {
          console.warn('Direct Spotify oembed note:', sErr);
        }
      }

      if (!fetchedData && videoId) {
        try {
          const oembedUrl = `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${videoId}&format=json`;
          const oResp = await fetch(oembedUrl);
          if (oResp.ok) {
            const oData = await oResp.json();
            fetchedData = {
              id: videoId,
              platform: 'youtube',
              url: `https://www.youtube.com/watch?v=${videoId}`,
              title: oData.title || 'YouTube Audio',
              author: oData.author_name || 'YouTube Creator',
              duration: null,
              duration_formatted: 'Ready to convert',
              thumbnail: oData.thumbnail_url || `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
              view_count: 0
            };
          }
        } catch (oErr) {
          console.warn('Direct YouTube oembed fallback note:', oErr);
        }
      }

      if (!fetchedData) {
        throw new Error('Could not fetch track details. Please check the URL or ensure the backend server is running.');
      }

      currentVideoData = fetchedData;

      // Populate preview card
      previewThumb.src = currentVideoData.thumbnail || (videoId ? `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg` : '');
      previewDuration.textContent = currentVideoData.duration_formatted || 'Ready';
      editTitle.value = currentVideoData.title || (currentVideoData.platform === 'spotify' ? 'Spotify Track' : (currentVideoData.platform === 'instagram' ? 'Instagram Video' : 'YouTube Audio'));
      editArtist.value = currentVideoData.author || (currentVideoData.platform === 'spotify' ? 'Spotify Artist' : (currentVideoData.platform === 'instagram' ? 'Instagram' : 'YouTube'));

      if (platformBadge) {
        if (currentVideoData.platform === 'spotify') {
          platformBadge.textContent = 'Spotify Track';
          platformBadge.className = 'platform-badge-tag spotify';
        } else if (currentVideoData.platform === 'instagram') {
          platformBadge.textContent = 'Instagram Reel/Post';
          platformBadge.className = 'platform-badge-tag instagram';
        } else {
          platformBadge.textContent = 'YouTube Video';
          platformBadge.className = 'platform-badge-tag youtube';
        }
      }

      if (currentVideoData.duration) {
        trimEnd.max = currentVideoData.duration;
      }

      previewCard.style.display = 'block';
      previewCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      showToast('Video details loaded! Ready to convert.', 'success');

    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      fetchBtn.disabled = false;
      fetchBtn.innerHTML = `
        <span>Fetch</span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="5" y1="12" x2="19" y2="12"></line>
          <polyline points="12 5 19 12 12 19"></polyline>
        </svg>
      `;
    }
  }

  // --- API: Convert to MP3 / MP4 ---

  convertBtn.addEventListener('click', async () => {
    if (!currentVideoData) return;

    const payload = {
      url: currentVideoData.url,
      format: selectedFormat,
      quality: qualitySelect.value,
      title: editTitle.value.trim(),
      artist: editArtist.value.trim(),
      embed_thumbnail: embedCoverCheck.checked,
      trim_start: trimStart.value ? parseFloat(trimStart.value) : null,
      trim_end: trimEnd.value ? parseFloat(trimEnd.value) : null
    };

    // UI State for Conversion
    previewCard.style.display = 'none';
    resultCard.style.display = 'none';
    progressCard.style.display = 'block';
    progressPct.textContent = '0%';
    progressBar.style.width = '0%';
    progressStatus.textContent = selectedFormat === 'mp4' ? 'Connecting to video converter...' : 'Connecting to audio converter...';
    progressCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    try {
      const resp = await fetch('/api/convert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const res = await resp.json();
      if (!resp.ok) {
        throw new Error(res.detail || 'Failed to start conversion');
      }

      activeJobId = res.job_id;
      pollJobProgress(activeJobId);

    } catch (err) {
      showToast(err.message, 'error');
      progressCard.style.display = 'none';
      previewCard.style.display = 'block';
    }
  });

  function pollJobProgress(jobId) {
    if (activePollInterval) clearInterval(activePollInterval);

    activePollInterval = setInterval(async () => {
      try {
        const resp = await fetch(`/api/progress/${jobId}`);
        if (!resp.ok) {
          clearInterval(activePollInterval);
          throw new Error('Conversion job timed out or failed to track.');
        }

        const job = await resp.json();

        // Update progress UI
        const pct = job.progress || 0;
        progressPct.textContent = `${pct}%`;
        progressBar.style.width = `${pct}%`;
        progressStatus.textContent = job.status_text || 'Processing audio stream...';

        if (job.status === 'completed') {
          clearInterval(activePollInterval);
          onConversionComplete(job);
        } else if (job.status === 'error') {
          clearInterval(activePollInterval);
          progressCard.style.display = 'none';
          previewCard.style.display = 'block';
          
          let friendlyMsg = job.error || 'Conversion failed. Please try again.';
          if (friendlyMsg.includes('Sign in to confirm') || friendlyMsg.includes('bot')) {
            friendlyMsg = selectedFormat === 'mp4'
              ? 'Video stream could not be loaded. Please try again in a few moments or try another link.'
              : 'Audio stream could not be loaded. Please try again in a few moments or try another link.';
          }
          showToast(friendlyMsg, 'error');
        }
      } catch (err) {
        clearInterval(activePollInterval);
        progressCard.style.display = 'none';
        previewCard.style.display = 'block';
        showToast(err.message, 'error');
      }
    }, 700);
  }

  function onConversionComplete(job) {
    progressCard.style.display = 'none';
    resultCard.style.display = 'block';
    resultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    const isMp4 = job.format === 'mp4';

    // Populate result card
    resultThumb.src = job.thumbnail || currentVideoData?.thumbnail || '';
    resultTitle.textContent = job.title;
    resultArtist.textContent = job.artist || (isMp4 ? 'Video File' : 'Audio Track');
    resultBitrate.textContent = job.quality || (isMp4 ? '720p HD' : '320 kbps');
    resultSize.textContent = job.file_size_formatted || (isMp4 ? 'Video File' : 'Audio File');
    resultDuration.textContent = job.duration_formatted || '';

    // Setup download button
    const downloadUrl = `/api/download/${job.id}`;
    downloadBtn.href = downloadUrl;
    downloadBtn.setAttribute('download', job.filename || `${job.title}.${isMp4 ? 'mp4' : 'mp3'}`);
    if (downloadBtnText) {
      downloadBtnText.textContent = isMp4 ? 'Download MP4 Video' : 'Download MP3 Audio';
    }

    // Setup Media Player
    const streamUrl = `/api/stream/${job.id}`;
    if (isMp4) {
      pauseAudio();
      if (audioPlayerBox) audioPlayerBox.style.display = 'none';
      if (resultVideo) {
        resultVideo.style.display = 'block';
        resultVideo.src = streamUrl;
      }
      showToast('MP4 Video ready! Play preview or download below.', 'success');
    } else {
      if (resultVideo) {
        resultVideo.pause();
        resultVideo.src = '';
        resultVideo.style.display = 'none';
      }
      if (audioPlayerBox) audioPlayerBox.style.display = 'block';
      nativeAudio.src = streamUrl;
      nativeAudio.load();
      resetAudioPlayer();
      showToast('Conversion ready! Click Download MP3 or play preview below.', 'success');
    }

    // Setup Copy Link
    copyLinkBtn.onclick = () => {
      const fullUrl = `${window.location.origin}${downloadUrl}`;
      navigator.clipboard.writeText(fullUrl).then(() => {
        showToast('Direct download link copied to clipboard!', 'success');
      });
    };

    loadHistory();
  }

  // --- Audio Preview Player Logic ---

  function resetAudioPlayer() {
    pauseAudio();
    audioSeeker.value = 0;
    audioCurrentTime.textContent = '0:00';
    audioTotalTime.textContent = '0:00';
  }

  function playAudio() {
    nativeAudio.play().then(() => {
      playIcon.style.display = 'none';
      pauseIcon.style.display = 'block';
    }).catch(err => {
      console.warn('Playback error:', err);
    });
  }

  function pauseAudio() {
    nativeAudio.pause();
    playIcon.style.display = 'block';
    pauseIcon.style.display = 'none';
  }

  playerPlayBtn.addEventListener('click', () => {
    if (nativeAudio.paused) {
      playAudio();
    } else {
      pauseAudio();
    }
  });

  nativeAudio.addEventListener('loadedmetadata', () => {
    audioTotalTime.textContent = formatTime(nativeAudio.duration);
  });

  nativeAudio.addEventListener('timeupdate', () => {
    if (!isNaN(nativeAudio.duration) && nativeAudio.duration > 0) {
      const pct = (nativeAudio.currentTime / nativeAudio.duration) * 100;
      audioSeeker.value = pct;
      audioCurrentTime.textContent = formatTime(nativeAudio.currentTime);
    }
  });

  nativeAudio.addEventListener('ended', () => {
    pauseAudio();
    audioSeeker.value = 0;
    audioCurrentTime.textContent = '0:00';
  });

  audioSeeker.addEventListener('input', () => {
    if (!isNaN(nativeAudio.duration) && nativeAudio.duration > 0) {
      const seekTo = (audioSeeker.value / 100) * nativeAudio.duration;
      nativeAudio.currentTime = seekTo;
    }
  });

  // --- Convert Another Video ---

  convertAnotherBtn.addEventListener('click', () => {
    pauseAudio();
    if (resultVideo) {
      resultVideo.pause();
      resultVideo.src = '';
      resultVideo.style.display = 'none';
    }
    resultCard.style.display = 'none';
    previewCard.style.display = 'none';
    progressCard.style.display = 'none';
    urlInput.value = '';
    clearBtn.style.display = 'none';
    currentVideoData = null;
    activeJobId = null;
    dropZone.scrollIntoView({ behavior: 'smooth', block: 'center' });
    urlInput.focus();
  });

  // --- History Management ---

  async function loadHistory() {
    try {
      const resp = await fetch('/api/history');
      if (!resp.ok) return;
      const data = await resp.json();
      renderHistory(data.history || []);
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  }

  function renderHistory(items) {
    if (!items || items.length === 0) {
      historyList.innerHTML = `<div class="empty-history">No converted files yet in this session. Drop a YouTube, Spotify, or Instagram link above!</div>`;
      return;
    }

    historyList.innerHTML = items.map(item => {
      const isMp4 = item.format === 'mp4';
      return `
      <div class="history-item">
        <img class="history-thumb" src="${escapeHtml(item.thumbnail)}" alt="Cover" onerror="this.src='data:image/svg+xml,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'52\' height=\'52\' fill=\'%23333\'><rect width=\'52\' height=\'52\'/></svg>'">
        <div class="history-details">
          <div class="history-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</div>
          <div class="history-sub">
            <span class="meta-pill format-badge ${isMp4 ? 'mp4' : 'mp3'}">${escapeHtml((item.format || 'mp3').toUpperCase())}</span>
            <span>${escapeHtml(item.artist || (isMp4 ? 'Video File' : 'Audio Track'))}</span>
            <span>•</span>
            <span>${escapeHtml(item.file_size_formatted || '')}</span>
            <span>•</span>
            <span>${escapeHtml(item.quality || (isMp4 ? '720p HD' : '320 kbps'))}</span>
          </div>
        </div>
        <div class="history-actions">
          <button class="btn-icon history-play-btn" data-id="${item.id}" data-format="${item.format || 'mp3'}" title="Preview">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          </button>
          <a href="/api/download/${item.id}" download="${escapeHtml(item.filename || (isMp4 ? 'video.mp4' : 'audio.mp3'))}" class="btn-icon" title="Download">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
          </a>
          <button class="btn-icon history-del-btn" data-id="${item.id}" title="Delete file">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </div>
      </div>
    `;}).join('');

    // Attach listeners for history action buttons
    document.querySelectorAll('.history-play-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        const fmt = btn.getAttribute('data-format') || 'mp3';
        const streamUrl = `/api/stream/${id}`;
        
        if (fmt === 'mp4') {
          pauseAudio();
          if (audioPlayerBox) audioPlayerBox.style.display = 'none';
          if (resultVideo) {
            resultVideo.style.display = 'block';
            resultVideo.src = streamUrl;
            resultVideo.play().catch(e => console.warn(e));
          }
          resultCard.style.display = 'block';
          if (resultVideo) resultVideo.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          showToast('Playing MP4 video preview', 'info');
        } else {
          if (resultVideo) {
            resultVideo.pause();
            resultVideo.src = '';
            resultVideo.style.display = 'none';
          }
          if (audioPlayerBox) audioPlayerBox.style.display = 'block';
          nativeAudio.src = streamUrl;
          playAudio();
          resultCard.style.display = 'block';
          showToast('Playing MP3 audio preview', 'info');
        }
      });
    });

    document.querySelectorAll('.history-del-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        try {
          await fetch(`/api/history/${id}`, { method: 'DELETE' });
          loadHistory();
          showToast('Removed from history', 'info');
        } catch (err) {
          showToast('Failed to delete history item', 'error');
        }
      });
    });
  }

  clearHistoryBtn.addEventListener('click', async () => {
    try {
      const resp = await fetch('/api/history');
      if (resp.ok) {
        const data = await resp.json();
        for (const item of (data.history || [])) {
          await fetch(`/api/history/${item.id}`, { method: 'DELETE' });
        }
        loadHistory();
        showToast('All conversion history cleared', 'info');
      }
    } catch (err) {
      console.error(err);
    }
  });

  // --- Navigation Links Smooth Scroll & Active Indicator ---
  document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
      const targetId = link.getAttribute('href');
      if (targetId && targetId.startsWith('#')) {
        const targetEl = document.querySelector(targetId);
        if (targetEl) {
          e.preventDefault();
          targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
          document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
          link.classList.add('active');
        }
      }
    });
  });

  // Initial load
  loadHistory();
});
