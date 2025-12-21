(function () {
  let myChart = null;

  // ローカルストレージに設定を保存
  function saveSettings() {
    const settings = [];
    for (let i = 1; i <= 3; i++) {
      const on = document.getElementById(`line-${i}-on`)?.checked;
      const type = document.getElementById(`line-${i}-type`)?.value;
      const period = document.getElementById(`line-${i}-period`)?.value;
      if (on !== undefined) settings.push({ on, type, period });
    }
    localStorage.setItem('sfbuff_ema_settings', JSON.stringify(settings));
  }

  // 保存された設定を読み込み
  function loadSettings() {
    const saved = localStorage.getItem('sfbuff_ema_settings');
    if (saved) return JSON.parse(saved);
    // デフォルト値
    return [
      { on: true, type: 'EMA', period: 300 },
      { on: false, type: 'EMA', period: 100 },
      { on: false, type: 'SMA', period: 200 },
    ];
  }

  // 設定用UIの作成
  function createUI(container) {
    if (document.getElementById('sfbuff-settings-panel')) return;
    const currentSettings = loadSettings();
    const uiBase = document.createElement('div');
    uiBase.id = 'sfbuff-settings-panel';
    uiBase.style = `background: #2a2a2a; border: 1px solid #444; border-radius: 8px; padding: 12px; margin: 10px 0; color: #fff; font-size: 12px; font-family: sans-serif; box-shadow: 0 4px 6px rgba(0,0,0,0.3); clear: both;`;

    let html =
      '<h3 style="margin:0 0 10px 0; font-size:14px; color:#aaa;">移動平均設定 (試合数)</h3><div style="display:flex; gap:8px; flex-wrap:wrap;">';
    const colors = ['#ff6384', '#36a2eb', '#4bc0c0'];

    for (let i = 1; i <= 3; i++) {
      const conf = currentSettings[i - 1] || {
        on: false,
        type: 'EMA',
        period: 100,
      };
      html += `<div style="background:#333; padding:8px; border-radius:4px; flex:1; min-width:180px; border-left: 4px solid ${
        colors[i - 1]
      };">
                <label style="font-weight:bold; display:block; margin-bottom:4px;"><input type="checkbox" id="line-${i}-on" ${
        conf.on ? 'checked' : ''
      }> Line ${i}</label>
                <div style="display:flex; gap:4px; align-items:center;">
                    <select id="line-${i}-type" style="background:#444; color:#fff; border:1px solid #666; font-size:11px;">
                        <option value="EMA" ${
                          conf.type === 'EMA' ? 'selected' : ''
                        }>EMA</option>
                        <option value="SMA" ${
                          conf.type === 'SMA' ? 'selected' : ''
                        }>SMA</option>
                    </select>
                    <input type="number" id="line-${i}-period" value="${
        conf.period
      }" style="width:45px; background:#444; color:#fff; border:1px solid #666; font-size:11px;">
                    <span>試合</span>
                </div>
            </div>`;
    }
    html +=
      '</div><button id="update-graph-btn" style="margin-top:10px; padding:6px 12px; background:#007bff; color:#fff; border:none; border-radius:4px; cursor:pointer; font-weight:bold;">グラフを更新・設定保存</button>';

    uiBase.innerHTML = html;
    container.parentNode.insertBefore(uiBase, container);

    document.getElementById('update-graph-btn').onclick = e => {
      e.preventDefault();
      saveSettings();
      injectEMAGraph();
    };
  }

  // メインの描画処理
  function injectEMAGraph() {
    // SFBuffが持ってる生データを探す
    const chartDiv = document.querySelector('[data-chartjs-data-value]');
    if (!chartDiv) return;
    let rawData;
    try {
      rawData = JSON.parse(chartDiv.getAttribute('data-chartjs-data-value'));
    } catch (e) {
      return;
    }

    // MRのデータセットを特定
    const mrDataset = rawData.data.datasets.find(
      ds => ds.yAxisID?.toLowerCase().includes('mr') || ds.label === 'MR'
    );
    if (!mrDataset) return;

    // 欠損値を除去して配列化
    const originalData = mrDataset.data.filter(p => p.y !== null);
    const yValues = originalData.map(d => d.y);
    const dateStrings = originalData.map(d => d.x);

    createUI(chartDiv);

    // 単純移動平均(SMA)の計算
    const calculateSMA = (v, n) =>
      v.map((_, i) =>
        i < n - 1 ? null : v.slice(i - n + 1, i + 1).reduce((a, b) => a + b) / n
      );

    // 指数平滑移動平均(EMA)の計算
    const calculateEMA = (v, n) => {
      if (!v.length) return [];
      const alpha = 2 / (n + 1);
      let res = [v[0]];
      for (let i = 1; i < v.length; i++)
        res.push((v[i] - res[i - 1]) * alpha + res[i - 1]);
      return res;
    };

    // 生MRの線（背景として薄く表示）
    const finalDatasets = [
      {
        label: '生MR',
        data: yValues,
        borderColor: 'rgba(255,255,255,0.15)',
        borderWidth: 1,
        pointRadius: 1,
        order: 10,
      },
    ];

    // ユーザー設定に基づいて移動平均線を追加
    const colors = ['#ff6384', '#36a2eb', '#4bc0c0'];
    for (let i = 1; i <= 3; i++) {
      const onElem = document.getElementById(`line-${i}-on`);
      if (onElem && onElem.checked) {
        const type = document.getElementById(`line-${i}-type`).value;
        const period =
          parseInt(document.getElementById(`line-${i}-period`).value) || 1;
        const data =
          type === 'EMA'
            ? calculateEMA(yValues, period)
            : calculateSMA(yValues, period);
        finalDatasets.push({
          label: `${type}(${period})`,
          data: data,
          borderColor: colors[i - 1],
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.2,
        });
      }
    }

    // X軸のラベル（日付）
    const allLabels = dateStrings.map(d => {
      const date = new Date(d);
      return isNaN(date.getTime())
        ? d
        : `${date.getMonth() + 1}/${date.getDate()}`;
    });

    // 元のグラフを隠してカスタムキャンバスを表示
    chartDiv.style.display = 'none';
    let canvas = document.getElementById('emaChart');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'emaChart';
      canvas.style =
        'width:100%; max-height:420px; background:#1a1a1a; margin-top:10px; border-radius:4px;';
      chartDiv.parentNode.appendChild(canvas);
    }

    // 再描画時は前のインスタンスを破棄
    if (myChart) myChart.destroy();
    myChart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: { labels: allLabels, datasets: finalDatasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          // 左Y軸
          y: {
            position: 'left',
            grid: {
              // 50刻みを強調、25刻みは補助線
              color: c => (c.tick.value % 50 === 0 ? '#777' : '#555'),
              lineWidth: c => (c.tick.value % 50 === 0 ? 1 : 0.5),
              drawTicks: true,
            },
            ticks: {
              color: '#aaa',
              font: { size: 10 },
              stepSize: 25,
            },
          },
          // 右Y軸（左と同期）
          y2: {
            position: 'right',
            grid: { display: false },
            ticks: {
              color: '#aaa',
              font: { size: 10 },
              stepSize: 25,
            },
            afterDataLimits: axis => {
              axis.min = axis.chart.scales.y.min;
              axis.max = axis.chart.scales.y.max;
            },
          },
          // X軸（グリッド表示あり）
          x: {
            grid: {
              display: true,
              color: '#333',
              lineWidth: 0.5,
            },
            ticks: {
              color: '#aaa',
              maxRotation: 0,
              font: { size: 10 },
              autoSkip: true,
              maxTicksLimit: 20,
            },
          },
        },
        plugins: {
          legend: {
            labels: { color: '#fff', boxWidth: 10, font: { size: 11 } },
          },
          tooltip: {
            callbacks: {
              // ツールチップにフル形式の日時を表示
              title: context =>
                new Date(dateStrings[context[0].dataIndex]).toLocaleString(),
            },
          },
        },
      },
    });
  }

  // SFBuffのページ遷移や検索によるDOM変化を監視
  const globalObserver = new MutationObserver(mutations => {
    for (let mutation of mutations) {
      if (
        mutation.target.querySelector?.('[data-chartjs-data-value]') ||
        (mutation.type === 'attributes' &&
          mutation.attributeName === 'data-chartjs-data-value')
      ) {
        injectEMAGraph();
        break;
      }
    }
  });

  globalObserver.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['data-chartjs-data-value'],
  });

  // 初回実行
  setTimeout(injectEMAGraph, 1000);
})();
