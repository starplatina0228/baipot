<template>
  <div class="gantt-chart-container">
    <vue-apex-charts
      v-if="series.length > 0"
      type="rangeBar"
      height="100%"
      :options="chartOptions"
      :series="series"
    ></vue-apex-charts>
    <div v-else class="no-data-message">
      No data available to display the chart.
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import VueApexCharts from 'vue3-apexcharts';

const props = defineProps({
  scheduleData: {
    type: Array,
    required: true,
  },
  startDate: {
    type: String,
    required: true,
  },
});

const series = computed(() => {
  if (!props.scheduleData || props.scheduleData.length === 0) return [];

  // Group ships by their berth position
  const shipsByBerth = props.scheduleData.reduce((acc, ship) => {
    const berth = `Berth at ${Math.round(ship.Position_m)}m`;
    if (!acc[berth]) {
      acc[berth] = [];
    }
    acc[berth].push(ship);
    return acc;
  }, {});

  // Create a series for each berth
  return Object.entries(shipsByBerth).map(([berth, ships]) => ({
    name: berth,
    data: ships.map(ship => {
      const start = new Date(props.startDate).getTime() + ship.Start_h * 60 * 60 * 1000;
      const end = new Date(props.startDate).getTime() + ship.Completion_h * 60 * 60 * 1000;
      return {
        x: ship.Ship,
        y: [start, end],
      };
    }),
  }));
});

const chartOptions = computed(() => ({
  chart: {
    type: 'rangeBar',
    height: '100%',
    toolbar: {
        show: true,
    }
  },
  plotOptions: {
    bar: {
      horizontal: true,
      barHeight: '50%',
      rangeBarGroupRows: true,
    },
  },
  xaxis: {
    type: 'datetime',
    labels: {
      datetimeUTC: false, // Display in local time
    },
  },
  yaxis: {
    show: true,
  },
  tooltip: {
    x: {
      format: 'dd MMM HH:mm',
    },
  },
  fill: {
    type: 'gradient',
    gradient: {
      shade: 'light',
      type: 'vertical',
      shadeIntensity: 0.25,
      gradientToColors: undefined,
      inverseColors: true,
      opacityFrom: 1,
      opacityTo: 1,
      stops: [50, 0, 100, 100],
    },
  },
  legend: {
    position: 'top',
    horizontalAlign: 'left',
  },
}));

</script>

<style scoped>
.gantt-chart-container, .no-data-message {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}
.no-data-message {
    color: #868e96;
}
</style>
