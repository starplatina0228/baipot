<template>
  <div class="etd-calculator-wrapper">
    <div class="etd-calculator">
      <div class="etd-header">
        <h2>단일 선박 ETD 계산</h2>
        <p class="etd-subtitle">선박의 정보를 입력하여 예상 출항 시간을 계산합니다.</p>
      </div>

      <!-- Step Indicator -->
      <div class="step-indicator">
        <div :class="['step', { active: step >= 1, completed: step > 1 }]">선사 선택</div>
        <div :class="['step', { active: step >= 2, completed: step > 2 }]">선명 선택</div>
        <div :class="['step', { active: step >= 3, completed: step > 3 }]">ETA 선택</div>
        <div :class="['step', { active: step >= 4, completed: step > 4 }]">정보 확인 및 계산</div>
      </div>

      <!-- Step 1: Select Shipping Line -->
      <div v-if="step === 1" class="etd-form-step">
        <div class="form-group">
          <label>선사</label>
          <input v-model="selectedShippingLine" @focus="showShippingLineDropdown = true" placeholder="선사를 선택하세요">
          <div v-if="showShippingLineDropdown" class="dropdown">
            <div v-for="line in shippingLines" :key="line" @click="selectShippingLine(line)" class="dropdown-item">
              {{ line }}
            </div>
          </div>
        </div>
        <div class="step-actions">
          <button @click="nextStep" :disabled="!selectedShippingLine">다음</button>
        </div>
      </div>

      <!-- Step 2: Select Ship Name -->
      <div v-if="step === 2" class="etd-form-step">
        <div class="form-group">
          <label>선명</label>
          <input v-model="etdRequestData.ship_name" @focus="showShipNameDropdown = true" placeholder="선명을 선택하세요">
          <div v-if="showShipNameDropdown" class="dropdown">
            <div v-for="ship in shipNames" :key="ship.ship_name" @click="selectShipName(ship)" class="dropdown-item">
              {{ ship.ship_name }}
            </div>
          </div>
        </div>
        <div class="step-actions">
          <button @click="prevStep">이전</button>
          <button @click="nextStep" :disabled="!etdRequestData.ship_name">다음</button>
        </div>
      </div>

      <!-- Step 3: Select ETA -->
      <div v-if="step === 3" class="etd-form-step">
        <div class="form-group">
          <label>도착예정시간 (ETA)</label>
          <date-picker 
            v-model:value="etdRequestData.eta" 
            type="datetime" 
            format="YYYY-MM-DD HH:mm"
            value-type="date" 
            placeholder="Select ETA"
            :disabled-date="disablePastDates"
            confirm
            confirm-text="OK"
          ></date-picker>
        </div>
        <div class="step-actions">
          <button @click="prevStep">이전</button>
          <button @click="nextStep" :disabled="!etdRequestData.eta">다음</button>
        </div>
      </div>

      <!-- Step 4: Review and Calculate -->
      <div v-if="step === 4" class="etd-form-step">
        <div class="review-table">
          <div class="review-row">
            <div class="review-label">선사</div>
            <div class="review-value">{{ etdRequestData.shipping_company }}</div>
          </div>
          <div class="review-row">
            <div class="review-label">선명</div>
            <div class="review-value">{{ etdRequestData.ship_name }}</div>
          </div>
          <div class="review-row">
            <div class="review-label">ETA</div>
            <div class="review-value">{{ etdRequestData.eta ? etdRequestData.eta.toLocaleString() : '' }}</div>
          </div>
        </div>
        <div class="etd-form">
          <div class="form-column">
            <div class="form-group">
              <label>선박 길이 (m)</label>
              <input type="number" v-model.number="etdRequestData.ship_length" @input="validateShipLength">
               <p v-if="shipLengthError" class="error-message">{{ shipLengthError }}</p>
            </div>
            <div class="form-group">
              <label>총톤수</label>
              <input type="number" v-model.number="etdRequestData.gross_tonnage">
            </div>
          </div>
          <div class="form-column">
            <div class="form-group">
              <label>Shift</label>
              <input type="number" v-model.number="etdRequestData.shift">
            </div>
            <div class="form-group">
              <label>양하물량</label>
              <input type="number" v-model.number="etdRequestData.cargo_unload">
            </div>
            <div class="form-group">
              <label>적하물량</label>
              <input type="number" v-model.number="etdRequestData.cargo_load">
            </div>
          </div>
        </div>
        <div class="step-actions">
          <button @click="prevStep">이전</button>
          <button @click="calculateEtdWrapper" :disabled="etdLoading || shipLengthError">ETD 계산</button>
        </div>
      </div>
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
       <div class="schedule-table-container">
        <h3>전체 선석 스케줄</h3>
        <table class="schedule-table">
          <thead>
            <tr>
              <th>선사</th>
              <th>선명</th>
              <th>접안 시간</th>
              <th>완료 시간</th>
              <th>선석</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ship in etdResult" :key="ship.merge_key" :class="{ 'highlighted-ship-row': ship.merge_key === highlightKey }">
              <td>{{ ship.shipping_company }}</td>
              <td>{{ ship.Ship }}</td>
              <td>{{ formatDatetime(ship.Start_dt) }}</td>
              <td>{{ formatDatetime(ship.Completion_dt) }}</td>
              <td>{{ ship.berth }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useSchedule } from '../composables/useSchedule.js';
import DatePicker from 'vue-datepicker-next';
import 'vue-datepicker-next/index.css';
import GanttChart from './GanttChart.vue';

const {
  ships,
  etdRequestData,
  etdResult,
  etdLoading,
  etdError,
  calculateEtd,
} = useSchedule();

const step = ref(1);
const selectedShippingLine = ref('');
const showShippingLineDropdown = ref(false);
const showShipNameDropdown = ref(false);
const shipLengthError = ref('');

const shippingLines = computed(() => {
  if (!ships.value) return [];
  const lines = ships.value.map(ship => ship.shipping_company);
  return [...new Set(lines)];
});

const shipNames = computed(() => {
  if (!ships.value || !selectedShippingLine.value) return [];
  return ships.value.filter(ship => ship.shipping_company === selectedShippingLine.value);
});

watch(selectedShippingLine, (newLine, oldLine) => {
  if (newLine !== oldLine) {
    etdRequestData.value.ship_name = '';
    etdRequestData.value.shipping_company = newLine;
  }
});

function selectShippingLine(line) {
  selectedShippingLine.value = line;
  showShippingLineDropdown.value = false;
}

function selectShipName(ship) {
  etdRequestData.value.ship_name = ship.ship_name;
  etdRequestData.value.ship_length = ship.LOA;
  etdRequestData.value.gross_tonnage = ship.gross_tonnage;
  showShipNameDropdown.value = false;
}

function nextStep() {
  if (step.value < 4) {
    step.value++;
  }
}

function prevStep() {
  if (step.value > 1) {
    step.value--;
  }
}

function disablePastDates(date) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return date < today;
}

function validateShipLength() {
  if (etdRequestData.value.ship_length > 1150) {
    shipLengthError.value = '선박 길이는 1150을 넘을 수 없습니다.';
  } else {
    shipLengthError.value = '';
  }
}

async function calculateEtdWrapper() {
  await calculateEtd();
  step.value = 5; // Move to result view
}

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
  const baseDate = new Date(eta.getFullYear(), eta.getMonth(), eta.getDate() - 1);

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
.etd-calculator-wrapper {
  padding: 2rem 1.5rem;
  margin: 2rem;
}

.etd-calculator {
  background: #ffffff;
  border-radius: 12px;
  padding: 2rem 2rem;
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

.step-indicator {
  display: flex;
  justify-content: space-around;
  margin-bottom: 2rem;
}

.step {
  padding: 0.5rem 1rem;
  border-radius: 8px;
  background-color: #f0f0f0;
  color: #999;
  font-weight: 500;
}

.step.active {
  background-color: #e7f3ff;
  color: #007bff;
}

.step.completed {
  background-color: #d4edda;
  color: #155724;
}

.etd-form-step {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-group {
  position: relative;
  display: flex;
  flex-direction: column;
}

.form-group label {
  font-weight: 500;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
  color: #34495e;
}

.form-group input {
  padding: 0.65rem 0.85rem;
  border: 1px solid #ced4da;
  border-radius: 6px;
  font-size: 0.9rem;
}

.dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #ced4da;
  border-radius: 6px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 10;
}

.dropdown-item {
  padding: 0.5rem 1rem;
  cursor: pointer;
}

.dropdown-item:hover {
  background-color: #f0f0f0;
}

.step-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 1rem;
}

.step-actions button {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  background-color: #007bff;
  color: white;
  cursor: pointer;
}

.step-actions button:disabled {
  background-color: #b0b6bb;
  cursor: not-allowed;
}

.review-table {
  border: 1px solid #e9ecef;
  border-radius: 8px;
  margin-bottom: 1.5rem;
}

.review-row {
  display: flex;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #e9ecef;
}
.review-row:last-child {
  border-bottom: none;
}

.review-label {
  font-weight: 600;
  width: 120px;
  color: #495057;
}

.review-value {
  color: #212529;
}

.etd-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}

.error-message {
  color: #dc3545;
  font-size: 0.8rem;
  margin-top: 0.25rem;
}

.etd-result-wrapper {
  margin-top: 2rem;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border: 1px solid #e9ecef;
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

.gantt-chart-container {
  height: 500px;
  padding: 1rem;
}

.schedule-table-container {
  padding: 1rem;
}

.schedule-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
}

.schedule-table th, .schedule-table td {
  border: 1px solid #e9ecef;
  padding: 0.75rem;
  text-align: left;
}

.schedule-table th {
  background-color: #f8f9fa;
}

.highlighted-ship-row {
  background-color: #e7f3ff;
}
</style>