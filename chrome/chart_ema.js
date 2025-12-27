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
    // X軸の設定も配列の末尾にオブジェクトとして詰め込む（構造を大きく変えないため）
    const xAxisType = document.getElementById('x-axis-type')?.value || 'date';
    localStorage.setItem(
      'sfbuff_ema_settings',
      JSON.stringify({ lines: settings, xAxisType })
    );
  }

  // 保存された設定を読み込み
  function loadSettings() {
    const saved = localStorage.getItem('sfbuff_ema_settings');
    if (saved) {
      const parsed = JSON.parse(saved);
      // 旧バージョン（配列のみ）との互換性維持
      if (Array.isArray(parsed)) return { lines: parsed, xAxisType: 'date' };
      return parsed;
    }
    return {
      lines: [
        { on: true, type: 'EMA', period: 300 },
        { on: false, type: 'EMA', period: 100 },
        { on: false, type: 'SMA', period: 200 },
      ],
      xAxisType: 'date',
    };
  }

  // 設定用UIの作成
  function createUI(container) {
    if (document.getElementById('sfbuff-settings-panel')) return;
    const config = loadSettings();
    const uiBase = document.createElement('div');
    uiBase.id = 'sfbuff-settings-panel';
    uiBase.style = `background: #2a2a2a; border: 1px solid #444; border-radius: 8px; padding: 12px; margin: 10px 0; color: #fff; font-size: 12px; font-family: sans-serif; box-shadow: 0 4px 6px rgba(0,0,0,0.3); clear: both;`;

    let html = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <h3 style="margin:0; font-size:14px; color:#aaa;">移動平均設定</h3>
        <div style="background:#333; padding:4px 8px; border-radius:4px;">
          <span style="margin-right:8px;">X軸表示:</span>
          <select id="x-axis-type" style="background:#444; color:#fff; border:1px solid #666; font-size:11px;">
            <option value="date" ${
              config.xAxisType === 'date' ? 'selected' : ''
            }>日付</option>
            <option value="count" ${
              config.xAxisType === 'count' ? 'selected' : ''
            }>試合数</option>
          </select>
        </div>
      </div>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">`;

    const colors = ['#ff6384', '#36a2eb', '#4bc0c0'];

    for (let i = 1; i <= 3; i++) {
      const conf = config.lines[i - 1] || {
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
  // メインの描画処理
  function injectEMAGraph() {
    const chartDiv = document.querySelector('[data-chartjs-data-value]');
    if (!chartDiv) return;
    let rawData;
    try {
      rawData = JSON.parse(chartDiv.getAttribute('data-chartjs-data-value'));
    } catch (e) {
      return;
    }

    const mrDataset = rawData.data.datasets.find(
      ds => ds.yAxisID?.toLowerCase().includes('mr') || ds.label === 'MR'
    );
    if (!mrDataset) return;

    const originalData = mrDataset.data.filter(p => p.y !== null);
    const yValues = originalData.map(d => d.y);
    const dateStrings = originalData.map(d => d.x);

    createUI(chartDiv);
    const config = loadSettings();
    const xAxisType =
      document.getElementById('x-axis-type')?.value || config.xAxisType;

    // 計算ロジック
    const calculateSMA = (v, n) =>
      v.map((_, i) =>
        i < n - 1 ? null : v.slice(i - n + 1, i + 1).reduce((a, b) => a + b) / n
      );
    const calculateEMA = (v, n) => {
      if (!v.length) return [];
      const alpha = 2 / (n + 1);
      let res = [v[0]];
      for (let i = 1; i < v.length; i++)
        res.push((v[i] - res[i - 1]) * alpha + res[i - 1]);
      return res;
    };

    // データの整形（x: index+1, y: MR値 のオブジェクト配列にする）
    const formatData = values => values.map((y, i) => ({ x: i + 1, y: y }));

    const finalDatasets = [
      {
        label: '生MR',
        data: formatData(yValues),
        borderColor: 'rgba(255,255,255,0.15)',
        borderWidth: 1,
        pointRadius: 1,
        order: 10,
      },
    ];

    const colors = ['#ff6384', '#36a2eb', '#4bc0c0'];
    for (let i = 1; i <= 3; i++) {
      const onElem = document.getElementById(`line-${i}-on`);
      if (onElem && onElem.checked) {
        const type = document.getElementById(`line-${i}-type`).value;
        const period =
          parseInt(document.getElementById(`line-${i}-period`).value) || 1;
        const calculatedData =
          type === 'EMA'
            ? calculateEMA(yValues, period)
            : calculateSMA(yValues, period);

        finalDatasets.push({
          label: `${type}(${period})`,
          data: formatData(calculatedData),
          borderColor: colors[i - 1],
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.2,
        });
      }
    }

    chartDiv.style.display = 'none';
    let canvas = document.getElementById('emaChart');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'emaChart';
      canvas.style =
        'width:100%; max-height:420px; background:#1a1a1a; margin-top:10px; border-radius:4px;';
      chartDiv.parentNode.appendChild(canvas);
    }

    if (myChart) myChart.destroy();
    myChart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: { datasets: finalDatasets }, // labelsは使わずdataset内のxを利用
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            position: 'left',
            grid: {
              color: c => (c.tick.value % 50 === 0 ? '#777' : '#555'),
              lineWidth: c => (c.tick.value % 50 === 0 ? 1 : 0.5),
              drawTicks: true,
            },
            ticks: { color: '#aaa', font: { size: 10 }, stepSize: 25 },
          },
          y2: {
            position: 'right',
            grid: { display: false },
            ticks: { color: '#aaa', font: { size: 10 }, stepSize: 25 },
            afterDataLimits: axis => {
              axis.min = axis.chart.scales.y.min;
              axis.max = axis.chart.scales.y.max;
            },
          },
          x: {
            type: xAxisType === 'count' ? 'linear' : 'category',
            // 日付モードの時だけラベルを流し込む
            labels:
              xAxisType === 'date'
                ? dateStrings.map(d => {
                    const date = new Date(d);
                    return isNaN(date.getTime())
                      ? d
                      : `${date.getMonth() + 1}/${date.getDate()}`;
                  })
                : undefined,
            // 試合数モードの時、右端をデータ数に強制固定
            min: xAxisType === 'count' ? 1 : undefined,
            max: xAxisType === 'count' ? yValues.length : undefined,
            grid: { display: true, color: '#333', lineWidth: 0.5 },
            ticks: {
              color: '#aaa',
              font: { size: 10 },
              maxRotation: 0,
              autoSkip: true,
              maxTicksLimit: xAxisType === 'date' ? 20 : 10,
            },
            // 軸の計算が終わった直後に目盛りを書き換える
            afterTickToLabelConversion: axis => {
              if (xAxisType === 'count') {
                const lastVal = yValues.length;
                // 最後の目盛りが最大値でなければ、最後を書き換えるか追加する
                const ticks = axis.ticks;
                if (
                  ticks.length > 0 &&
                  ticks[ticks.length - 1].value !== lastVal
                ) {
                  // 右端に余裕がない場合は最後の目盛りを上書き、余裕があれば追加
                  if (lastVal - ticks[ticks.length - 1].value < lastVal * 0.1) {
                    ticks[ticks.length - 1].value = lastVal;
                    ticks[ticks.length - 1].label = lastVal.toString();
                  } else {
                    ticks.push({ value: lastVal, label: lastVal.toString() });
                  }
                }
              }
            },
          },
        },
        plugins: {
          legend: {
            labels: { color: '#fff', boxWidth: 10, font: { size: 11 } },
          },
          tooltip: {
            callbacks: {
              // ツールチップのタイトルを日付に固定（indexから復元）
              title: context => {
                const idx = context[0].dataIndex;
                return new Date(dateStrings[idx]).toLocaleString();
              },
            },
          },
        },
      },
    });
  }

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

  setTimeout(injectEMAGraph, 1000);
})();
