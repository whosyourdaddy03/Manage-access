<template>
  <div class="app-container dashboard-container">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :xs="12" :sm="6" :lg="3">
        <div class="stat-card-item">
          <div class="stat-value">{{ statTotalEpochs }}</div>
          <div class="stat-label">训练总轮次</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6" :lg="3">
        <div class="stat-card-item">
          <div class="stat-value">{{ statDatasetCount }}</div>
          <div class="stat-label">数据集数量</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6" :lg="3">
        <div class="stat-card-item">
          <div class="stat-value">{{ statLatestMap50 }}</div>
          <div class="stat-label">最新 mAP50</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6" :lg="3">
        <div class="stat-card-item">
          <div class="stat-value">{{ statLatestMap5095 }}</div>
          <div class="stat-label">最新 mAP50-95</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6" :lg="3">
        <div class="stat-card-item">
          <div class="stat-value">{{ statLatestPrecision }}</div>
          <div class="stat-label">最新 Precision</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6" :lg="3">
        <div class="stat-card-item">
          <div class="stat-value">{{ statLatestRecall }}</div>
          <div class="stat-label">最新 Recall</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6" :lg="3">
        <div class="stat-card-item">
          <div class="stat-value">{{ statLatestTrainLoss }}</div>
          <div class="stat-label">最新 Train Loss</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6" :lg="3">
        <div class="stat-card-item">
          <div class="stat-value">{{ statLatestValLoss }}</div>
          <div class="stat-label">最新 Val Loss</div>
        </div>
      </el-col>
    </el-row>

    <!-- ID选择器 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="24">
        <el-card>
          <div slot="header">
            <span><i class="el-icon-s-data"></i> 训练结果概览</span>
            <div style="float: right;">
              <span style="margin-right: 10px; font-size: 13px; color: #606266;">选择训练ID:</span>
              <el-select v-model="selectedId" placeholder="请选择训练ID" size="small" style="width: 200px;" @change="onIdChange">
                <el-option label="全部数据" value="" />
                <el-option v-for="id in epochIds" :key="id" :label="'训练ID: ' + id" :value="id" />
              </el-select>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20">
      <el-col :xs="24" :lg="12" style="margin-bottom: 20px;">
        <el-card>
          <div slot="header"><span>Loss 变化趋势</span></div>
          <div ref="lossChart" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12" style="margin-bottom: 20px;">
        <el-card>
          <div slot="header"><span>mAP 变化趋势</span></div>
          <div ref="mapChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>
    <el-row :gutter="20">
      <el-col :xs="24" :lg="12" style="margin-bottom: 20px;">
        <el-card>
          <div slot="header"><span>Precision / Recall 变化趋势</span></div>
          <div ref="prChart" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12" style="margin-bottom: 20px;">
        <el-card>
          <div slot="header"><span>Learning Rate 变化趋势</span></div>
          <div ref="lrChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import * as echarts from 'echarts'
require('echarts/theme/macarons')
import { queryAllEpochIds, queryEpochResults, queryEpochResultsByGroup } from '@/api/visualization/epoch'

export default {
  name: 'Dashboard',
  data() {
    return {
      epochIds: [],
      selectedId: '',
      allResults: [],
      currentResults: [],
      statTotalEpochs: 0,
      statDatasetCount: 0,
      statLatestMap50: '--',
      statLatestMap5095: '--',
      statLatestPrecision: '--',
      statLatestRecall: '--',
      statLatestTrainLoss: '--',
      statLatestValLoss: '--',
      lossChart: null,
      mapChart: null,
      prChart: null,
      lrChart: null
    }
  },
  mounted() {
    this.fetchData()
  },
  beforeDestroy() {
    this.disposeCharts()
  },
  methods: {
    fetchData() {
      this.$nextTick(() => {
        queryAllEpochIds().then(response => {
          this.epochIds = response.data || []
        }).catch(() => {})

        queryEpochResults().then(response => {
          const data = (response.data || []).sort((a, b) => a.epoch - b.epoch)
          this.allResults = data
          this.currentResults = data
          this.updateStats(data)
          this.$nextTick(() => {
            this.initCharts(data)
          })
        }).catch(() => {})
      })
    },
    onIdChange(id) {
      if (!id) {
        this.currentResults = this.allResults
        this.updateStats(this.allResults)
        this.$nextTick(() => {
          this.updateCharts(this.allResults)
        })
        return
      }
      queryEpochResultsByGroup(id).then(response => {
        const data = (response.data || []).sort((a, b) => a.epoch - b.epoch)
        this.currentResults = data
        this.updateStats(data)
        this.$nextTick(() => {
          this.updateCharts(data)
        })
      }).catch(() => {})
    },
    updateStats(data) {
      if (!data || data.length === 0) {
        this.statTotalEpochs = 0
        this.statDatasetCount = 0
        this.statLatestMap50 = '--'
        this.statLatestMap5095 = '--'
        this.statLatestPrecision = '--'
        this.statLatestRecall = '--'
        this.statLatestTrainLoss = '--'
        this.statLatestValLoss = '--'
        return
      }
      this.statTotalEpochs = data.length
      // 统计不同的id数量
      const ids = new Set(data.map(d => d.id))
      this.statDatasetCount = ids.size
      // 取最后一条数据作为最新的
      const last = data[data.length - 1]
      this.statLatestMap50 = last.metrics_mAP50_B != null ? Number(last.metrics_mAP50_B).toFixed(4) : '--'
      this.statLatestMap5095 = last.metrics_mAP50_95_B != null ? Number(last.metrics_mAP50_95_B).toFixed(4) : '--'
      this.statLatestPrecision = last.metrics_precision_B != null ? Number(last.metrics_precision_B).toFixed(4) : '--'
      this.statLatestRecall = last.metrics_recall_B != null ? Number(last.metrics_recall_B).toFixed(4) : '--'
      this.statLatestTrainLoss = last.train_box_loss != null ? Number(last.train_box_loss).toFixed(4) : '--'
      this.statLatestValLoss = last.val_box_loss != null ? Number(last.val_box_loss).toFixed(4) : '--'
    },
    initCharts(data) {
      this.initLossChart(data)
      this.initMapChart(data)
      this.initPRChart(data)
      this.initLRChart(data)
    },
    updateCharts(data) {
      this.updateLossChart(data)
      this.updateMapChart(data)
      this.updatePRChart(data)
      this.updateLRChart(data)
    },
    disposeCharts() {
      if (this.lossChart) { this.lossChart.dispose(); this.lossChart = null }
      if (this.mapChart) { this.mapChart.dispose(); this.mapChart = null }
      if (this.prChart) { this.prChart.dispose(); this.prChart = null }
      if (this.lrChart) { this.lrChart.dispose(); this.lrChart = null }
    },
    // Loss 折线图
    initLossChart(data) {
      const dom = this.$refs.lossChart
      if (!dom) return
      this.lossChart = echarts.init(dom, 'macarons')
      this.updateLossChart(data)
    },
    updateLossChart(data) {
      if (!this.lossChart) return
      const epochs = data.map(d => 'E' + d.epoch)
      const option = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['train_box_loss', 'val_box_loss', 'train_cls_loss', 'val_cls_loss'], top: 0 },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: epochs, axisLabel: { rotate: 45, fontSize: 10 } },
        yAxis: { type: 'value', name: 'Loss' },
        series: [
          { name: 'train_box_loss', type: 'line', smooth: true, data: data.map(d => d.train_box_loss) },
          { name: 'val_box_loss', type: 'line', smooth: true, data: data.map(d => d.val_box_loss) },
          { name: 'train_cls_loss', type: 'line', smooth: true, data: data.map(d => d.train_cls_loss) },
          { name: 'val_cls_loss', type: 'line', smooth: true, data: data.map(d => d.val_cls_loss) }
        ]
      }
      this.lossChart.setOption(option, true)
    },
    // mAP 折线图
    initMapChart(data) {
      const dom = this.$refs.mapChart
      if (!dom) return
      this.mapChart = echarts.init(dom, 'macarons')
      this.updateMapChart(data)
    },
    updateMapChart(data) {
      if (!this.mapChart) return
      const epochs = data.map(d => 'E' + d.epoch)
      const option = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['mAP50', 'mAP50-95'], top: 0 },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: epochs, axisLabel: { rotate: 45, fontSize: 10 } },
        yAxis: { type: 'value', name: 'mAP', min: 0, max: 1 },
        series: [
          { name: 'mAP50', type: 'line', smooth: true, data: data.map(d => d.metrics_mAP50_B) },
          { name: 'mAP50-95', type: 'line', smooth: true, data: data.map(d => d.metrics_mAP50_95_B) }
        ]
      }
      this.mapChart.setOption(option, true)
    },
    // Precision/Recall 折线图
    initPRChart(data) {
      const dom = this.$refs.prChart
      if (!dom) return
      this.prChart = echarts.init(dom, 'macarons')
      this.updatePRChart(data)
    },
    updatePRChart(data) {
      if (!this.prChart) return
      const epochs = data.map(d => 'E' + d.epoch)
      const option = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['Precision', 'Recall'], top: 0 },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: epochs, axisLabel: { rotate: 45, fontSize: 10 } },
        yAxis: { type: 'value', name: 'Value', min: 0, max: 1 },
        series: [
          { name: 'Precision', type: 'line', smooth: true, data: data.map(d => d.metrics_precision_B) },
          { name: 'Recall', type: 'line', smooth: true, data: data.map(d => d.metrics_recall_B) }
        ]
      }
      this.prChart.setOption(option, true)
    },
    // Learning Rate 折线图
    initLRChart(data) {
      const dom = this.$refs.lrChart
      if (!dom) return
      this.lrChart = echarts.init(dom, 'macarons')
      this.updateLRChart(data)
    },
    updateLRChart(data) {
      if (!this.lrChart) return
      const epochs = data.map(d => 'E' + d.epoch)
      const option = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['lr_pg0', 'lr_pg1', 'lr_pg2'], top: 0 },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: epochs, axisLabel: { rotate: 45, fontSize: 10 } },
        yAxis: { type: 'value', name: 'LR' },
        series: [
          { name: 'lr_pg0', type: 'line', smooth: true, data: data.map(d => d.lr_pg0) },
          { name: 'lr_pg1', type: 'line', smooth: true, data: data.map(d => d.lr_pg1) },
          { name: 'lr_pg2', type: 'line', smooth: true, data: data.map(d => d.lr_pg2) }
        ]
      }
      this.lrChart.setOption(option, true)
    }
  }
}
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
  background: #f5f7fa;
  min-height: calc(100vh - 84px);
}
.stat-cards {
  margin-bottom: 20px;
}
.stat-card-item {
  background: #fff;
  border-radius: 8px;
  padding: 18px 12px;
  text-align: center;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  border: 1px solid #ebeef5;
  transition: all 0.3s;
}
.stat-card-item:hover {
  box-shadow: 0 6px 16px rgba(0, 21, 41, 0.12);
  transform: translateY(-3px);
  border-color: #409eff;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #409eff;
  line-height: 1.4;
}
.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  font-weight: 500;
}
.chart-container {
  width: 100%;
  height: 350px;
}
</style>
