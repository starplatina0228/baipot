<template>
  <!-- ETD Calculator Section -->
  <div class="etd-calculator-wrapper">
    <div class="etd-calculator">
      <div class="etd-header">
        <h2>단일 선박 ETD 계산</h2>
      </div>
      <p class="etd-subtitle">선박의 정보를 입력하여 예상 출항 시간을 계산합니다.</p>

      <div class="etd-form">
        <div class="form-column">
          <div class="form-group">
            <label>선명</label>
            <input v-model="etdRequestData.ship_name" placeholder="e.g., HYUNDAI TOKYO">
          </div>
          <div class="form-group">
            <label>선사</label>
            <input v-model="etdRequestData.shipping_company" placeholder="e.g., HMM">
          </div>
          <div class="form-group">
            <label>선박 길이 (m)</label>
            <input type="number" v-model.number="etdRequestData.ship_length" placeholder="e.g., 150">
          </div>
          <div class="form-group">
            <label>총톤수</label>
            <input type="number" v-model.number="etdRequestData.gross_tonnage" placeholder="e.g., 50000">
          </div>
        </div>
        <div class="form-column">
          <div class="form-group">
            <label>Shift</label>
            <input type="number" v-model.number="etdRequestData.shift" placeholder="e.g., 0">
          </div>
          <div class="form-group">
            <label>양하물량</label>
            <input type="number" v-model.number="etdRequestData.cargo_unload" placeholder="e.g., 100">
          </div>
          <div class="form-group">
            <label>적하물량</label>
            <input type="number" v-model.number="etdRequestData.cargo_load" placeholder="e.g., 100">
          </div>
          <div class="form-group">
            <label>도착예정시간 (ETA)</label>
            <date-picker 
              v-model:value="etdRequestData.eta" 
              type="datetime" 
              format="YYYY-MM-DD HH:mm"
              value-type="date" 
              placeholder="Select ETA"
              confirm
              confirm-text="OK"
            ></date-picker>
          </div>
        </div>
      </div>
      
      <button @click="calculateEtd" :disabled="etdLoading" class="calculate-btn">
        <span v-if="etdLoading" class="spinner"></span>
        ETD 계산
      </button>
    </div>

    <!-- ETD Result Display -->
    <div v-if="etdLoading" class="etd-loading">
      <div class="spinner"></div>
      <span>ETD를 계산하는 중입니다...</span>
    </div>
    <div v-if="etdError" class="error-message etd-error">
      {{ etdError }}
    </div>
    <div v-if="etdResult" class="etd-result-wrapper">
      <div class="etd-result-header">
        <h3>계산 결과</h3>
        <button @click="etdResult = null" class="close-btn">&times;</button>
      </div>
      
      <!-- Highlighted Ship Numeric Data -->
      <div v-if="highlightedShipData" class="etd-result-body">
        <div class="result-item main-result">
          <span class="result-label">{{ highlightedShipData.Ship }}</span>
          <span class="result-value">{{ formatDatetime(highlightedShipData.Start_dt) }} ~ {{ formatDatetime(highlightedShipData.Completion_dt) }}</span>
        </div>
        <div class="result-item">
          <span class="result-label">예상 대기 시간</span>
          <span class="result-value">{{ highlightedShipData.Waiting_h.toFixed(2) }} 시간</span>
        </div>
        <div class="result-item">
          <span class="result-label">배정 선석 위치</span>
          <span class="result-value">{{ highlightedShipData.Position_m.toFixed(2) }}m</span>
        </div>
      </div>

      <div class="gantt-chart-container">
        <gantt-chart 
          v-if="ganttData" 
          :schedule-data="ganttData.scheduleData" 
          :start-date="ganttData.startDate"
          :highlighted-ship-key="highlightKey"
        ></gantt-chart>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useSchedule } from '../composables/useSchedule.js';
import DatePicker from 'vue-datepicker-next';
import 'vue-datepicker-next/index.css';
import GanttChart from './GanttChart.vue';

const {
  etdRequestData,
  etdResult,
  etdLoading,
  etdError,
  calculateEtd,
} = useSchedule();

const highlightKey = computed(() => {
  if (!etdRequestData.value) return null;
  return `${etdRequestData.value.shipping_company}_${etdRequestData.value.ship_name.replace(/\s+/g, '')}`;
});

const highlightedShipData = computed(() => {
  if (!etdResult.value || !highlightKey.value) return null;
  return etdResult.value.find(ship => ship.merge_key === highlightKey.value);
});

const ganttData = computed(() => {
  if (!etdResult.value || etdResult.value.length === 0) return null;

  const eta = new Date(etdRequestData.value.eta);
  const baseDate = new Date(eta.getFullYear(), eta.getMonth(), eta.getDate() - 1); // Start chart from one day before ETA for context

  return {
    scheduleData: etdResult.value,
    startDate: baseDate.toISOString().slice(0, 10),
  };
});

const formatDatetime = (isoString) => {
  if (!isoString) return 'N/A';
  const date = new Date(isoString);
  return date.toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

</script>

<style scoped>
/* ETD Calculator Styles */
.etd-calculator-wrapper {
  padding: 1rem 1.5rem;
}

.etd-calculator {
  background: #ffffff;
  border-radius: 12px;
  padding: 1.5rem 2rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border: 1px solid #e9ecef;
}

.etd-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: #2c3e50;
}

.etd-subtitle {
  margin-top: 0;
  margin-bottom: 1.5rem;
  color: #576574;
  font-size: 0.95rem;
}

.etd-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}

.form-column {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group label {
  font-weight: 500;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
  color: #34495e;
}

.form-group input,
.form-group .mx-datepicker {
  width: 100%;
}

.form-group input {
  padding: 0.65rem 0.85rem;
  border: 1px solid #ced4da;
  border-radius: 6px;
  font-size: 0.9rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.form-group input:focus {
  outline: none;
  border-color: #80bdff;
  box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
}

.calculate-btn {
  width: 100%;
  font-size: 1rem;
  font-weight: 600;
  padding: 0.85rem 1rem;
  border-radius: 8px;
  background-color: #007bff;
  color: white;
  border: none;
  cursor: pointer;
  transition: background-color 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.calculate-btn:hover:not(:disabled) {
  background-color: #0056b3;
}

.calculate-btn:disabled {
  background-color: #a0c7e4;
  cursor: not-allowed;
}

/* ETD Result Styles */
.etd-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 2rem;
  font-size: 1rem;
  color: #576574;
}

.etd-error {
  margin: 1rem 1.5rem 0;
}

.etd-result-wrapper {
  margin: 1.5rem 0 0;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border: 1px solid #e9ecef;
  overflow: hidden;
}

.etd-result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.5rem;
  background-color: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.etd-result-header h3 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.5rem;
  line-height: 1;
  color: #6c757d;
  transition: color 0.2s;
}

.close-btn:hover {
  color: #212529;
}

.etd-result-body {
  padding: 1.5rem;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  border-bottom: 1px solid #e9ecef;
}

.result-item {
  background-color: #f8f9fa;
  padding: 1rem;
  border-radius: 8px;
}

.result-item.main-result {
  grid-column: 1 / -1;
  background-color: #e7f3ff;
  border-left: 5px solid #007bff;
}

.result-item.main-result .result-label {
  font-size: 1.1rem;
  font-weight: 700;
  color: #004085;
}

.result-label {
  font-size: 0.9rem;
  color: #6c757d;
  display: block;
  margin-bottom: 0.25rem;
}

.result-value {
  font-size: 1rem;
  font-weight: 600;
  color: #212529;
}

.gantt-chart-container {
  height: 500px; /* Give it a fixed height */
  padding: 1rem;
}
</style>