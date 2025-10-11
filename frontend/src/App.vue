<template>
  <div id="app">
    <header>
      <div class="controls">
        <div v-if="viewMode === 'list'" class="search-group">
          <div class="date-picker">
            <label for="start-date">Start Date:</label>
            <date-picker 
              v-model:value="startDate" 
              format="YYYY-MM-DD" 
              value-type="format"
              placeholder="Select Start Date"
              :disabled="loading"
            ></date-picker>
            <label for="end-date">End Date:</label>
            <date-picker 
              v-model:value="endDate" 
              format="YYYY-MM-DD" 
              value-type="format"
              placeholder="Select End Date"
              :disabled="loading"
            ></date-picker>
          </div>
          <button @click="prepareSchedule" :disabled="loading">
            <span v-if="loading" class="spinner"></span>
            검색
          </button>
        </div>

        <div v-if="viewMode === 'chart'" class="back-button-group">
            <button @click="showListView">
                &larr; Back to List
            </button>
            <h2>Optimization Result</h2>
        </div>

        <!-- Action Buttons -->
        <div v-if="!loading && viewMode === 'list'" class="buttons">
          <button @click="optimizeAll" :disabled="loading">
            <span v-if="loading" class="spinner"></span>
            전체 최적화
          </button>
          <button @click="optimizeSelected" :disabled="loading">
            <span v-if="loading" class="spinner"></span>
            선택 최적화
          </button>
        </div>

        <!-- Cancel Button -->
        <div v-if="loading" class="buttons">
            <button @click="cancelRequest" class="cancel-btn">
                요청 취소
            </button>
        </div>

      </div>
    </header>

    <div v-if="error" class="error-message">
      {{ error }}
    </div>

    <div class="results">
      <div v-if="viewMode === 'list'" class="table-container">
        <table v-if="results.length > 0">
          <thead>
            <tr>
              <th v-for="key in visibleKeys" :key="key">
                {{ columnNames[key] || key }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr 
              v-for="(row, index) in results" 
              :key="index" 
              @click="toggleSelection(row)" 
              :class="{ 
                'selected-row': row.selected,
                'average-value-row': row.uses_average_values
              }"
            >
              <td v-for="key in visibleKeys" :key="key">
                {{ formatValue(row[key]) }}
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else-if="!loading">No data to display.</div>
      </div>
      <gantt-chart 
        v-else-if="viewMode === 'chart' && optimizationResults" 
        :schedule-data="optimizationResults" 
        :start-date="startDate"
      ></gantt-chart>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useSchedule } from './composables/useSchedule.js';
import DatePicker from 'vue-datepicker-next';
import 'vue-datepicker-next/index.css';
import GanttChart from './components/GanttChart.vue';

const {
  startDate,
  endDate,
  results,
  optimizationResults,
  loading,
  error,
  viewMode,
  prepareSchedule,
  optimizeAll,
  optimizeSelected,
  toggleSelection,
  showListView,
  cancelRequest,
} = useSchedule();

const columnNames = {
  predicted_work_time: '예상 작업소요시간(H)',
  // Add mappings for optimization results if needed
  'Ship': '선명',
  'Start_h': '계획 접안시간(H)',
  'Completion_h': '계획 완료시간(H)',
  'Waiting_h': '대기시간(H)',
  'Service_h': '작업 소요시간(H)',
  'Position_m': '접안 위치(m)',
};

const hiddenColumns = [
  'uses_average_values',
  '양적하물량',
  '입항시간',
  '입항요일',
  '입항분기',
  '입항계절',
  'selected',
  'merge_key',
  'Ship_ID',
  'Arrival_h',
  'Service_min',
  'Length_m',
  'End_Position_m'
];

const visibleKeys = computed(() => {
  if (results.value.length === 0) return [];
  return Object.keys(results.value[0]).filter(key => !hiddenColumns.includes(key));
});

const formatValue = (value) => {
  if (typeof value === 'number') {
    return Math.round(value);
  }
  return value;
};

</script>