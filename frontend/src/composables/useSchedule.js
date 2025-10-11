import { ref, onMounted, computed } from 'vue';
import axios from 'axios';

export function useSchedule() {
  const startDate = ref(new Date().toISOString().slice(0, 10));
  const endDate = ref(new Date(new Date().setDate(new Date().getDate() + 7)).toISOString().slice(0, 10));
  const results = ref([]);
  const optimizationResults = ref(null);
  const loading = ref(false);
  const error = ref(null);
  const viewMode = ref('list'); // 'list' or 'chart'
  const abortController = ref(null);

  const api = axios.create({
    baseURL: 'http://localhost:8000',
  });

  const selectedShips = computed(() => 
    results.value.filter(ship => ship.selected).map(ship => ship.merge_key)
  );

  const cancelRequest = () => {
    if (abortController.value) {
      abortController.value.abort();
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
        optimizationResults.value = response.data;
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
    cancelRequest, // Export the cancel function
  };
}
