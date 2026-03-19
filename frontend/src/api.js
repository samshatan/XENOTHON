import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || '/api'

export const uploadDocument = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  const response = await axios.post(`${BASE_URL}/upload`, formData)
  return response.data
}

export const getStatus = async (jobId) => {
  const response = await axios.get(`${BASE_URL}/status/${jobId}`)
  return response.data
}

export const getResult = async (jobId) => {
  const response = await axios.get(`${BASE_URL}/result/${jobId}`)
  return response.data
}

export const createSSEConnection = (jobId, onMessage, onError) => {
  const url = `${BASE_URL}/stream/${jobId}`
  const eventSource = new EventSource(url)
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data)
    onMessage(data)
  }
  eventSource.onerror = onError
  return eventSource
}
