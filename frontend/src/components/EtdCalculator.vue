<template>
  <div class="etd-calculator-wrapper">
    <div class="etd-calculator">
      <div class="etd-header">
        <h2>선박 ETD 예측 서비스</h2>
        <p class="etd-subtitle">선박의 정보를 입력하면 예상 출항 시간을 제공합니다.</p>
      </div>

      <div class="etd-form">
        <!-- Step 1: Select Shipping Line -->
        <div class="form-group">
          <label for="shipping-line-select">선사</label>
          <select id="shipping-line-select" v-model="etdRequestData.shipping_company">
            <option disabled value="">선사를 선택하세요</option>
            <option v-for="line in shippingLines" :key="line" :value="line">
              {{ line }}
            </option>
          </select>
        </div>

        <!-- Step 2: Select Ship Name -->
        <div class="form-group">
          <label for="ship-name-select">선명</label>
          <select id="ship-name-select" v-model="etdRequestData.ship_name" :disabled="!etdRequestData.shipping_company">
            <option disabled value="">선명을 선택하세요</option>
            <option v-for="ship in shipNames" :key="ship.ship_name" :value="ship.ship_name">
              {{ ship.ship_name }}
            </option>
          </select>
        </div>

        <!-- Step 3: Select ETA -->
        <div class="form-group">
          <label>도착예정시간 (ETA)</label>
          <date-picker 
            v-model:value="etdRequestData.eta" 
            type="datetime" 
            format="YYYY-MM-DD HH:mm"
            value-type="date" 
            placeholder="ETA를 선택하세요"
            :disabled="!etdRequestData.ship_name"
            :disabled-date="disablePastDates"
            confirm
            confirm-text="OK"
          ></date-picker>
        </div>
        
        <!-- Step 4: Review and Calculate -->
        <div v-if="canCalculate" class="calculation-section">
          <div class="review-table">
            <div class="review-row">
              <div class="review-label">선박 길이 (m)</div>
              <div class="review-value">
                <input type="number" v-model.number="etdRequestData.ship_length" @input="validateShipLength">
              </div>
            </div>
             <div class="review-row" v-if="shipLengthError">
                <p class="error-message full-width">{{ shipLengthError }}</p>
            </div>
            <div class="review-row">
              <div class="review-label">총톤수</div>
              <div class="review-value">
                <input type="number" v-model.number="etdRequestData.gross_tonnage">
              </div>
            </div>
            <div class="review-row">
              <div class="review-label">Shift</div>
              <div class="review-value">
                <input type="number" v-model.number="etdRequestData.shift">
              </div>
            </div>
            <div class="review-row">
              <div class="review-label">양하물량</div>
              <div class="review-value">
                <input type="number" v-model.number="etdRequestData.cargo_unload">
              </div>
            </div>
            <div class="review-row">
              <div class="review-label">적하물량</div>
              <div class="review-value">
                <input type="number" v-model.number="etdRequestData.cargo_load">
              </div>
            </div>
          </div>
          <div class="step-actions">
            <button v-if="!etdLoading" @click="calculateEtd" :disabled="isCalculationDisabled">ETD 계산</button>
            <button v-else @click="cancelEtdRequest" class="cancel-btn">실행 취소</button>
          </div>
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
          <span class="result-label">예상 대기 시간 </span>
          <span class="result-value">{{ highlightedShipData.Waiting_h.toFixed(2) }} 시간</span>
        </div>
        <div class="result-item">
          <span class="result-label">배정 선석 위치 </span>
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
              <th>선명</th>
              <th>접안 시간</th>
              <th>완료 시간</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ship in etdResult" :key="ship.merge_key" :class="{ 'highlighted-ship-row': ship.merge_key === highlightKey }">
              <td>{{ ship.Ship }}</td>
              <td>{{ formatDatetime(ship.Start_dt) }}</td>
              <td>{{ formatDatetime(ship.Completion_dt) }}</td>
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
  ships, // This is now an object: { company: [ships...] }
  etdRequestData,
  etdResult,
  etdLoading,
  etdError,
  calculateEtd,
  cancelEtdRequest,
} = useSchedule();

const shipLengthError = ref('');

// Initialize request data structure
etdRequestData.value = {
  shipping_company: '',
  ship_name: '',
  eta: null,
  ship_length: 0,
  gross_tonnage: 0,
  shift: 0,
  cargo_unload: 0,
  cargo_load: 0,
};

const shippingLines = computed(() => {
  return Object.keys(ships.value || {});
});

const shipNames = computed(() => {
  const company = etdRequestData.value.shipping_company;
  if (!company || !ships.value[company]) return [];
  return ships.value[company];
});

// Watch for shipping company changes to reset ship name
watch(() => etdRequestData.value.shipping_company, (newCompany) => {
  etdRequestData.value.ship_name = '';
  etdRequestData.value.eta = null; // Also reset ETA
  shipLengthError.value = ''; // Clear potential errors
});

// Watch for ship name changes to auto-fill ship data
watch(() => etdRequestData.value.ship_name, (newShipName) => {
  if (newShipName) {
    const company = etdRequestData.value.shipping_company;
    const selectedShip = ships.value[company]?.find(ship => ship.ship_name === newShipName);
    if (selectedShip) {
      etdRequestData.value.ship_length = selectedShip.LOA;
      etdRequestData.value.gross_tonnage = selectedShip.gross_tonnage;
      validateShipLength(); // Validate length immediately after auto-filling
    }
  } else {
    // Clear fields if ship name is reset
    etdRequestData.value.ship_length = 0;
    etdRequestData.value.gross_tonnage = 0;
    shipLengthError.value = '';
  }
});

const canCalculate = computed(() => {
  return etdRequestData.value.shipping_company && etdRequestData.value.ship_name && etdRequestData.value.eta;
});

const isCalculationDisabled = computed(() => {
  if (etdLoading.value || shipLengthError.value) {
    return true;
  }
  const data = etdRequestData.value;
  // Disable if any required field for calculation is missing or invalid
  if (data.ship_length <= 0 || data.gross_tonnage <= 0) {
    return true;
  }
  // For cargo and shift, 0 is a valid value, so we just check for null/undefined.
  if (data.shift === null || data.shift === undefined ||
      data.cargo_unload === null || data.cargo_unload === undefined ||
      data.cargo_load === null || data.cargo_load === undefined) {
    return true;
  }
  return false;
});

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

const highlightKey = computed(() => {
  if (!etdRequestData.value || !etdRequestData.value.ship_name) return null;
  // The ship name is unique enough for the key within the result
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
  max-width: 800px;
  margin-left: auto;
  margin-right: auto;
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

.etd-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
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
.form-group select,
.mx-datepicker {
  width: 100%;
  padding: 0.65rem 0.85rem;
  border: 1px solid #ced4da;
  border-radius: 6px;
  font-size: 0.9rem;
  box-sizing: border-box;
}

.form-group select {
  background-color: white;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3e%3cpath fill='none' stroke='%23343a40' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M2 5l6 6 6-6'/%3e%3csvg%3e");
  background-repeat: no-repeat;
  background-position: right 0.75rem center;
  background-size: 16px 12px;
}

.form-group select:disabled {
  background-color: #e9ecef;
  cursor: not-allowed;
}

.calculation-section {
  margin-top: 1rem;
  border-top: 1px solid #e9ecef;
  padding-top: 2rem;
}

.step-actions {
  display: flex;
  justify-content: center;
  gap: 1rem;
  margin-top: 1rem;
}

.step-actions button {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  background-color: #007bff;
  color: white;
  cursor: pointer;
  font-size: 1rem;
}

.step-actions button.cancel-btn {
  background-color: #dc3545;
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
  align-items: center;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #e9ecef;
}
.review-row:last-child {
  border-bottom: none;
}

.review-label {
  font-weight: 600;
  width: 150px;
  color: #495057;
  flex-shrink: 0;
}

.review-value {
  color: #212529;
  flex-grow: 1;
}

.review-value input {
  width: 100%;
  border: none;
  padding: 0.5rem;
  border-radius: 4px;
}
.review-value input:focus {
  outline: 1px solid #007bff;
}

.error-message {
  color: #dc3545;
  font-size: 0.8rem;
  margin-top: 0.25rem;
}
.error-message.full-width {
    width: 100%;
    text-align: right;
    padding-right: 0.5rem;
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