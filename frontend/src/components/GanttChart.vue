<template>
  <div class="berth-chart-container">
    <!-- Y-Axis (Berth Position) -->
    <div class="y-axis">
      <div v-for="tick in yAxisTicks" :key="tick" class="y-axis-tick">{{ tick }}m</div>
    </div>

    <div class="chart-main-area">
      <!-- X-Axis (Time) -->
      <div class="x-axis" :style="{ gridTemplateColumns: `repeat(${chartData.days.length}, 1fr)` }">
        <div v-for="day in chartData.days" :key="day.getTime()" class="x-axis-day">{{ formatDate(day) }}</div>
      </div>

      <!-- Chart Body -->
      <div class="chart-body" @mousemove="handleChartMouseMove">
        <!-- Grid Lines -->
        <div class="grid-lines-y" :style="{ gridTemplateRows: `repeat(${yAxisTicks.length -1}, 1fr)` }">
            <div v-for="i in yAxisTicks.length - 1" :key="i" class="grid-line"></div>
        </div>
        <div class="grid-lines-x" :style="{ gridTemplateColumns: `repeat(${chartData.days.length}, 1fr)` }">
            <div v-for="i in chartData.days.length" :key="i" class="grid-line"></div>
        </div>

        <!-- Ship Blocks -->
        <div
          v-for="item in chartData.items"
          :key="item.ship.Ship_ID"
          class="ship-block"
          :class="{ 'highlighted-ship': item.ship.merge_key === highlightedShipKey }"
          :style="{
            top: item.top + '%',
            height: item.height + '%',
            left: item.left + '%',
            width: item.width + '%',
            backgroundColor: getShipColor(item.ship.Ship).main,
            borderColor: getShipColor(item.ship.Ship).border,
          }"
          @mouseenter="handleShipMouseEnter(item)"
          @mouseleave="handleShipMouseLeave"
        >
          <div class="ship-label">{{ item.ship.Ship }}</div>
        </div>

        <!-- Original Departure Marker (Dynamic) -->
        <div 
          v-if="hoveredItem && hoveredItem.ship.original_Completion_h"
          class="original-marker"
          :style="{
            top: hoveredItem.top + '%',
            height: hoveredItem.height + '%',
            left: getOriginalMarkerPosition(hoveredItem) + '%'
          }"
          :title="`원본 출항: ${getOriginalTime(hoveredItem.ship.original_Completion_h)}`"
        ></div>

      </div>
    </div>

    <!-- Custom Tooltip -->
    <div 
      v-if="tooltip.visible"
      class="custom-tooltip"
      :style="{ top: tooltip.top + 'px', left: tooltip.left + 'px' }"
    >
      <div class="tooltip-header">
        <strong>{{ tooltip.content.ship.Ship }}</strong>
      </div>
      <div class="tooltip-body">
        <div class="tooltip-row">
          <span class="tooltip-label">최적화된 기간</span>
          <span class="tooltip-value">{{ new Date(tooltip.content.startTime).toLocaleString() }} - {{ new Date(tooltip.content.endTime).toLocaleString() }}</span>
        </div>
        <div v-if="tooltip.content.ship.original_Start_h !== undefined && tooltip.content.ship.original_Completion_h !== undefined" class="tooltip-row">
          <span class="tooltip-label">크롤링된 기간</span>
          <span class="tooltip-value">{{ getOriginalTime(tooltip.content.ship.original_Start_h) }} - {{ getOriginalTime(tooltip.content.ship.original_Completion_h) }}</span>
        </div>
        <div class="tooltip-row">
          <span class="tooltip-label">선석 위치</span>
          <span class="tooltip-value">{{ tooltip.content.ship.Position_m }}m - {{ tooltip.content.ship.Position_m + tooltip.content.ship.Length_m }}m ({{ tooltip.content.ship.Length_m }}m)</span>
        </div>
        <div class="tooltip-row">
            <span class="tooltip-label">작업 시간</span>
            <span class="tooltip-value">{{ tooltip.content.ship.Service_h?.toFixed(2) }}h</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  scheduleData: {
    type: Array,
    required: true,
  },
  startDate: {
    type: String,
    required: true,
  },
  highlightedShipKey: {
    type: String,
    default: null,
  },
});

const Y_AXIS_TICK_INTERVAL = 100; // meters

// --- State for Hover Effects ---
const hoveredItem = ref(null);
const tooltip = ref({
  visible: false,
  content: { ship: {} }, // Initialize to prevent errors
  top: 0,
  left: 0,
});

const handleChartMouseMove = (event) => {
  if (tooltip.value.visible) {
    tooltip.value.top = event.pageY + 15;
    tooltip.value.left = event.pageX + 15;
  }
};

const handleShipMouseEnter = (item) => {
  hoveredItem.value = item;
  tooltip.value.content = item;
  tooltip.value.visible = true;
};

const handleShipMouseLeave = () => {
  hoveredItem.value = null;
  tooltip.value.visible = false;
};

// --- Chart Data Calculation ---
const chartData = computed(() => {
  if (!props.scheduleData || props.scheduleData.length === 0) {
    return { items: [], days: [], maxBerthPosition: 0, minDate: null, maxDate: null };
  }

  const ships = props.scheduleData.filter(s => s.Length_m > 0);
  if (ships.length === 0) {
      return { items: [], days: [], maxBerthPosition: 0, minDate: null, maxDate: null };
  }

  const baseTime = new Date(props.startDate).getTime();

  const itemsWithTimestamps = ships.map(ship => ({
    ship,
    startTime: baseTime + ship.Start_h * 3600 * 1000,
    endTime: baseTime + ship.Completion_h * 3600 * 1000,
  }));

  // X-Axis (Time) Calculation
  const minTimestamp = Math.min(...itemsWithTimestamps.map(item => item.startTime));
  const maxTimestamp = Math.max(...itemsWithTimestamps.map(item => item.endTime));
  const minDate = new Date(minTimestamp);
  minDate.setHours(0, 0, 0, 0);
  const maxDate = new Date(maxTimestamp);
  maxDate.setHours(23, 59, 59, 999);

  const days = [];
  if (maxDate.getTime() - minDate.getTime() > 0) {
      let currentDate = new Date(minDate);
      while (currentDate.getTime() <= maxDate.getTime()) {
        days.push(new Date(currentDate));
        currentDate.setDate(currentDate.getDate() + 1);
      }
  }

  // Y-Axis (Berth) Calculation
  const maxBerthPosition = Math.ceil(Math.max(...ships.map(s => s.Position_m + s.Length_m)) / Y_AXIS_TICK_INTERVAL) * Y_AXIS_TICK_INTERVAL;

  const items = itemsWithTimestamps.map(item => {
    const totalDuration = maxDate.getTime() - minDate.getTime();
    const left = totalDuration > 0 ? ((item.startTime - minDate.getTime()) / totalDuration) * 100 : 0;
    const width = totalDuration > 0 ? ((item.endTime - item.startTime) / totalDuration) * 100 : 0;
    const top = maxBerthPosition > 0 ? (item.ship.Position_m / maxBerthPosition) * 100 : 0;
    const height = maxBerthPosition > 0 ? (item.ship.Length_m / maxBerthPosition) * 100 : 0;

    return {
      ...item,
      left: Math.max(0, left),
      width: Math.max(0.1, width),
      top: Math.max(0, top),
      height: Math.max(0.1, height),
    };
  });

  return { items, days, maxBerthPosition, minDate, maxDate };
});

const getOriginalMarkerPosition = (item) => {
    if (!item || !item.ship.original_Completion_h || !chartData.value.minDate) return 0;

    const chartStartTime = chartData.value.minDate.getTime();
    const chartTotalDuration = chartData.value.maxDate.getTime() - chartStartTime;

    if (chartTotalDuration <= 0) return 0;

    const baseTime = new Date(props.startDate).getTime();
    const originalEndTime = baseTime + item.ship.original_Completion_h * 3600 * 1000;

    const leftPercentage = ((originalEndTime - chartStartTime) / chartTotalDuration) * 100;
    return leftPercentage;
};

const getOriginalTime = (timeInHours) => {
    if (timeInHours === undefined || timeInHours === null) return '';
    const baseTime = new Date(props.startDate).getTime();
    const time = baseTime + timeInHours * 3600 * 1000;
    return new Date(time).toLocaleString();
};

const yAxisTicks = computed(() => {
  if (chartData.value.maxBerthPosition === 0) return [0];
  const ticks = [];
  for (let i = 0; i <= chartData.value.maxBerthPosition; i += Y_AXIS_TICK_INTERVAL) {
    ticks.push(i);
  }
  return ticks;
});

const formatDate = (date) => {
  return `${date.getMonth() + 1}/${date.getDate()}`;
};

// --- Color Generation ---
const colorCache = {};
const getShipColor = (shipName) => {
  if (colorCache[shipName]) {
    return colorCache[shipName];
  }

  let hash = 0;
  for (let i = 0; i < shipName.length; i++) {
    hash = shipName.charCodeAt(i) + ((hash << 5) - hash);
    hash = hash & hash; // Convert to 32bit integer
  }

  const hue = hash % 360;
  const saturation = 70;
  const lightness = 50;

  const main = `hsla(${hue}, ${saturation}%, 45%, 0.9)`;
  const border = `hsla(${hue}, ${saturation}%, 35%, 1)`;

  const color = { main, border };
  colorCache[shipName] = color;
  return color;
};

</script>

<style scoped>
.berth-chart-container {
  display: flex;
  width: 100%;
  height: 100%;
  background-color: #fff;
  overflow: auto;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  position: relative; /* For tooltip positioning */
}

/* Y-Axis */
.y-axis {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 2rem 0 0.5rem 0;
  background-color: #f8f9fa;
  border-right: 1px solid #dee2e6;
}
.y-axis-tick {
  font-size: 0.75rem;
  color: #6c757d;
  text-align: right;
  padding-right: 0.5rem;
  position: relative;
}
.y-axis-tick:not(:last-child)::after {
    content: '';
    position: absolute;
    bottom: -1px;
    right: 0;
    width: 4px;
    height: 1px;
    background: #adb5bd;
}

/* Main Area */
.chart-main-area {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  min-width: 1500px;
}

/* X-Axis */
.x-axis {
  flex-shrink: 0;
  display: grid;
  border-bottom: 1px solid #dee2e6;
  background-color: #f8f9fa;
}
.x-axis-day {
  padding: 0.5rem 0;
  text-align: center;
  font-size: 0.8rem;
  font-weight: 600;
  color: #495057;
  border-right: 1px solid #e9ecef;
}
.x-axis-day:last-child { border-right: none; }

/* Chart Body */
.chart-body {
  flex-grow: 1;
  position: relative;
}

/* Grid Lines */
.grid-lines-y, .grid-lines-x {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    display: grid;
    pointer-events: none; /* Make sure grid doesn't block mouse events */
}
.grid-lines-y .grid-line {
    border-bottom: 1px dashed #e9ecef;
}
.grid-lines-x .grid-line {
    border-right: 1px solid #e9ecef;
}

/* Ship Block */
.ship-block {
  position: absolute;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  transition: transform 0.15s ease-in-out, filter 0.15s ease-in-out, box-shadow 0.2s ease-in-out;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border: 1px solid;
}
.ship-block:hover {
  z-index: 10;
  transform: scale(1.02);
  filter: brightness(1.1);
}

.highlighted-ship {
  z-index: 11; /* Make sure it's on top */
}

.highlighted-ship .ship-label {
  font-weight: 900; /* Extra bold */
  font-size: 0.85rem; /* Slightly larger */
  text-shadow: 1px 1px 3px rgba(0,0,0,0.7); /* More prominent shadow */
}

.ship-label {
  color: white;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.2rem 0.4rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
  pointer-events: none; /* Make sure label doesn't block mouse events */
}

/* Original Marker */
.original-marker {
  position: absolute;
  width: 0;
  border-left: 3px dashed rgba(220, 53, 69, 0.9);
  transform: translateX(-1.5px);
  z-index: 11; /* Higher than hovered ship-block */
  pointer-events: none;
  transition: opacity 0.2s ease-in-out;
}

/* Custom Tooltip */
.custom-tooltip {
  position: fixed; /* Use fixed to position relative to viewport */
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
  border: 1px solid #dee2e6;
  border-radius: 12px;
  padding: 1rem;
  box-shadow: 0 8px 24px rgba(0,0,0,0.15);
  z-index: 100;
  pointer-events: none; /* Prevent tooltip from capturing mouse events */
  font-size: 0.9rem;
  line-height: 1.6;
  min-width: 400px; /* Increased width */
  backdrop-filter: blur(10px);
  transition: opacity 0.2s ease;
}

.tooltip-header {
  font-size: 1.1rem;
  font-weight: 700;
  color: #212529;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #e9ecef;
  margin-bottom: 0.75rem;
}

.tooltip-body .tooltip-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.tooltip-label {
  font-weight: 600;
  color: #495057;
  margin-right: 1rem;
}

.tooltip-value {
  color: #212529;
  text-align: right;
}

</style>