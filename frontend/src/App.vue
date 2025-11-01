<template>
  <div id="app">
    <nav class="main-nav">
      <button @click="currentView = 'scheduling'" :class="{ active: currentView === 'scheduling' }">
        선석 스케줄링
      </button>
      <button @click="currentView = 'etd'" :class="{ active: currentView === 'etd' }">
        선박 ETD 예측 서비스
      </button>
    </nav>
    <main>
      <BerthScheduling v-if="currentView === 'scheduling'" />
      <EtdCalculator v-if="currentView === 'etd'" />
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import BerthScheduling from './components/BerthScheduling.vue';
import EtdCalculator from './components/EtdCalculator.vue';

const currentView = ref('scheduling'); // or 'etd'
</script>

<style>
/* Global styles that were in style.css */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  position: relative;
  font-weight: normal;
}

body {
  min-height: 100vh;
  color: #2c3e50;
  background: #f4f7f9;
  line-height: 1.6;
  font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
  font-size: 15px;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app-container {
  width: 100%;
  max-width: 95vw;
  margin: 0 auto;
}

.main-nav {
  display: flex;
  justify-content: center;
  background-color: #ffffff;
  border-bottom: 1px solid #dee2e6;
  padding: 0.5rem 1.5rem;
  border-radius: 0.75rem 0.75rem 0 0;
  margin-top: 2rem;
  box-shadow: 0 4px 10px rgba(0,0,0,0.05);
}

.main-nav button {
  padding: 0.75rem 1.5rem;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 500;
  color: #495057;
  transition: color 0.2s, border-bottom 0.2s;
  border-bottom: 3px solid transparent;
}

.main-nav button.active {
  color: #007bff;
  border-bottom-color: #007bff;
}

main {
  background-color: #ffffff;
  border-radius: 0 0 0.75rem 0.75rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  overflow: hidden;
}

/* Button Styles from style.css */
.search-group button,
.buttons button,
.back-button-group button {
  font-size: 0.9rem;
  font-weight: 500;
  padding: 0.55rem 1rem;
  border-radius: 0.375rem;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.search-group button, .back-button-group button { /* 검색, Back */
  background-color: #0d6efd;
  color: white;
}

.search-group button:hover, .back-button-group button:hover {
  background-color: #0b5ed7;
}

.buttons button.cancel-btn {
    background-color: #dc3545;
    color: white;
}

.buttons button.cancel-btn:hover {
    background-color: #bb2d3b;
}

.buttons button:nth-child(1) { /* 전체 최적화 */
  background-color: #6c757d;
  color: white;
}

.buttons button:nth-child(1):hover {
  background-color: #5c636a;
}

.buttons button:nth-child(2) { /* 선택 최적화 */
  background-color: #198754;
  color: white;
}

.buttons button:nth-child(2):hover {
  background-color: #157347;
}

.search-group button:disabled,
.buttons button:disabled,
.back-button-group button:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

/* Spinner */
.spinner {
  display: inline-block;
  width: 1em;
  height: 1em;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Datepicker customization */
.mx-datepicker {
  width: auto;
}

.mx-input {
  border: 1px solid #ced4da;
  border-radius: 0.375rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  box-shadow: none;
  transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
}

.mx-input:focus, .mx-input:hover {
  border-color: #86b7fe;
  box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25);
}

</style>