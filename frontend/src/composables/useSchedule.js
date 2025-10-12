import { ref, onMounted, computed } from 'vue';
import axios from 'axios';

export function useSchedule() {
  const startDate = ref(new Date().toISOString().slice(0, 10));
  const endDate = ref(new Date(new Date().setDate(new Date().getDate() + 5)).toISOString().slice(0, 10));
  const results = ref([]);
  const optimizationResults = ref(null);
  const loading = ref(false);
  const error = ref(null);
  const viewMode = ref('list'); // 'list' or 'chart'
  const abortController = ref(null);
  const etdAbortController = ref(null);

  // New state for ETD calculation
  const initialEtdRequestData = {
    ship_name: 'GLORY COIS',
    eta: new Date(new Date().setDate(new Date().getDate() + 3)),
    cargo_load: 300,
    cargo_unload: 300,
    ship_length: 150,
    shipping_company: 'COIS COMPANY',
    gross_tonnage: 3000,
    shift: 150
  };
  const etdRequestData = ref({ ...initialEtdRequestData });
  const etdResult = ref(null);
  const etdLoading = ref(false);
  const etdError = ref(null);

  const api = axios.create({
    baseURL: 'https://baipot-backend.onrender.com',
  });

  const selectedShips = computed(() => 
    results.value.filter(ship => ship.selected).map(ship => ship.merge_key)
  );

  const cancelRequest = () => {
    if (abortController.value) {
      abortController.value.abort();
    }
  };

  const cancelEtdRequest = () => {
    if (etdAbortController.value) {
      etdAbortController.value.abort();
    }
  };

  const fetchData = async (endpoint, data = {}) => {
    if (loading.value) {
      return; // Prevent multiple requests
    }

    loading.value = true;
    error.value = null;
    abortController.value = new AbortController();

    try {
      const payload = {
        start_date: startDate.value,
        end_date: endDate.value,
        ...data,
      };
      const response = await api.post(endpoint, payload, { signal: abortController.value.signal });

      if (endpoint === '/schedule/prepare') {
        results.value = response.data.map(item => ({
          ...item,
          selected: false,
          merge_key: `${item.선사}_${item.선명.replace(/\s+/g, '')}`
        }));
        optimizationResults.value = null; // Clear old optimization results
        viewMode.value = 'list';
      } else {
        const originalDataMap = new Map(results.value.map(ship => [ship.merge_key, ship]));

        const enrichedResults = response.data.map(optimizedShip => {
          const originalShip = originalDataMap.get(optimizedShip.merge_key);
          if (originalShip) {
            return {
              ...optimizedShip,
              original_Completion_h: originalShip.Completion_h,
              predicted_work_time: originalShip.predicted_work_time,
            };
          }
          return optimizedShip;
        });

        optimizationResults.value = enrichedResults;
        viewMode.value = 'chart';
      }

    } catch (err) {
      if (axios.isCancel(err)) {
        error.value = 'Request was canceled.';
      } else {
        error.value = `Error: ${err.response?.data?.detail || err.message}`;
      }
    } finally {
      loading.value = false;
      abortController.value = null;
    }
  };

  const calculateEtd = async () => {
    if (etdLoading.value) return;

    etdLoading.value = true;
    etdError.value = null;
    etdResult.value = null;
    
    etdAbortController.value = new AbortController();

    try {
      const response = await api.post('/schedule/calculate-etd', etdRequestData.value, { 
        signal: etdAbortController.value.signal 
      });
      etdResult.value = response.data;
    } catch (err) {
      if (axios.isCancel(err)) {
        etdError.value = 'ETD calculation was canceled.';
      } else {
        etdError.value = `Error: ${err.response?.data?.detail || err.message}`;
      }
    } finally {
      etdLoading.value = false;
      etdAbortController.value = null;
    }
  };

  const resetEtdCalculator = () => {
    etdRequestData.value = { ...initialEtdRequestData };
    etdResult.value = null;
    etdError.value = null;
    if (etdLoading.value) {
      cancelEtdRequest();
    }
  };

  const prepareSchedule = () => {
    fetchData('/schedule/prepare');
  };

  const optimizeAll = () => {
    fetchData('/schedule/optimize');
  };

  const optimizeSelected = () => {
    if (selectedShips.value.length === 0) {
      error.value = "Please select at least one ship to optimize.";
      return;
    }
    fetchData('/schedule/optimize-selected', { selected_ships: selectedShips.value });
  };

  const toggleSelection = (ship) => {
    if ('selected' in ship) {
      ship.selected = !ship.selected;
    }
  };

  const showListView = () => {
    viewMode.value = 'list';
  };

  onMounted(() => {
    prepareSchedule();
  });

  return {
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
    // New exports
    etdRequestData,
    etdResult,
    etdLoading,
    etdError,
    calculateEtd,
    cancelEtdRequest,
    resetEtdCalculator,
  };
}