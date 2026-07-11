<template>
  <div class="app-container training-detail-container">
    <!-- 顶部：返回按钮 + 任务信息 -->
    <el-card style="margin-bottom: 20px;">
      <div slot="header" class="card-header">
        <span><i class="el-icon-s-data"></i> 训练指标详情 - {{ taskId }}</span>
        <div style="float: right;">
          <el-button size="mini" icon="el-icon-arrow-left" @click="goBack">返回列表</el-button>
        </div>
      </div>

      <el-row :gutter="20" v-if="taskInfo">
        <el-col :span="4"><div class="info-label">模型版本</div><div class="info-value">{{ taskInfo.modelVersion || '--' }}</div></el-col>
        <el-col :span="5"><div class="info-label">训练时间</div><div class="info-value">{{ taskInfo.trainingTime || '--' }}</div></el-col>
        <el-col :span="3"><div class="info-label">Epochs</div><div class="info-value">{{ taskInfo.epochs || '--' }}</div></el-col>
        <el-col :span="3"><div class="info-label">Batch Size</div><div class="info-value">{{ taskInfo.batchSize || '--' }}</div></el-col>
        <el-col :span="3"><div class="info-label">Image Size</div><div class="info-value">{{ taskInfo.imageSize || '--' }}</div></el-col>
        <el-col :span="6"><div class="info-label">当前轮次</div><div class="info-value">{{ epochCount }} / {{ taskInfo.epochs || '?' }}</div></el-col>
      </el-row>
    </el-card>

    <!-- 指标趋势图 -->
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

    <!-- 模型产物列表 -->
    <el-card>
      <div slot="header"><span><i class="el-icon-download"></i> 模型产物列表</span></div>
      <el-table :data="modelFiles" stripe style="width: 100%">
        <el-table-column label="文件名" prop="name" min-width="300" />
        <el-table-column label="文件类型" prop="type" width="150" align="center">
          <template slot-scope="scope">
            <el-tag :type="scope.row.type === 'best' ? 'success' : 'info'">
              {{ scope.row.type === 'best' ? '最优模型' : '最近模型' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center">
          <template slot-scope="scope">
            <el-button type="primary" size="mini" icon="el-icon-download"
              :disabled="!scope.row.hasFile" @click="downloadFile(scope.row)">
              下载
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="modelFiles.length === 0" description="暂无模型文件配置" />
    </el-card>

    <div style="height: 20px;"></div>
  </div>
</template>

<script>
import * as echarts from 'echarts'
require('echarts/theme/macarons')
import { getTrainingDetail, getEpochResultsByTask, getDownloadUrl } from '@/api/visualization/training'

export default {
  name: 'TrainingDetail',
  data() {
    return {
      taskId: '',
      loading: false,
      taskInfo: null,
      epochData: [],
      epochCount: 0,
      lossChart: null,
      mapChart: null,
      prChart: null,
      lrChart: null,
      modelFiles: []
    }
  },
  created() {
    this.taskId = this.$route.params.id || ''
  },
  mounted() {
    if (this.taskId) {
      this.loadData()
    }
  },
  beforeDestroy() {
    this.disposeCharts()
  },
  methods: {
    loadData() {
      if (!this.taskId) return
      this.loading = true

      Promise.all([
        getTrainingDetail(this.taskId),
        getEpochResultsByTask(this.taskId)
      ]).then(([detailRes, epochRes]) => {
        this.taskInfo = detailRes.data
        const data = (epochRes.data || []).sort((a, b) => a.epoch - b.epoch)
        this.epochData = data
        this.epochCount = data.length

        // 构建模型文件列表
        this.modelFiles = [
          { name: 'best.pt', type: 'best', hasFile: !!(this.taskInfo && this.taskInfo.bestPtPath) },
          { name: 'last.pt', type: 'last', hasFile: !!(this.taskInfo && this.taskInfo.lastPtPath) }
        ]

        this.$nextTick(() => {
          this.initCharts(data)
        })
      }).catch(() => {
        this.$modal.msgError('加载训练数据失败')
      }).finally(() => {
        this.loading = false
      })
    },
    downloadFile(row) {
      const url = getDownloadUrl(this.taskId, row.type)
      // 创建隐藏 a 标签下载
      const a = document.createElement('a')
      a.href = url
      a.download = row.name
      a.style.display = 'none'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    },
    goBack() {
      this.$router.back()
    },
    // ===== ECharts 图表 =====
    initCharts(data) {
      this.initLossChart(data)
      this.initMapChart(data)
      this.initPRChart(data)
      this.initLRChart(data)
    },
    disposeCharts() {
      if (this.lossChart) { this.lossChart.dispose(); this.lossChart = null }
      if (this.mapChart) { this.mapChart.dispose(); this.mapChart = null }
      if (this.prChart) { this.prChart.dispose(); this.prChart = null }
      if (this.lrChart) { this.lrChart.dispose(); this.lrChart = null }
    },
    // Loss
    initLossChart(data) {
      const dom = this.$refs.lossChart
      if (!dom) return
      this.lossChart = echarts.init(dom, 'macarons')
      const epochs = data.map(d => 'E' + d.epoch)
      this.lossChart.setOption({
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
      }, true)
    },
    // mAP
    initMapChart(data) {
      const dom = this.$refs.mapChart
      if (!dom) return
      this.mapChart = echarts.init(dom, 'macarons')
      const epochs = data.map(d => 'E' + d.epoch)
      this.mapChart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['mAP50', 'mAP50-95'], top: 0 },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: epochs, axisLabel: { rotate: 45, fontSize: 10 } },
        yAxis: { type: 'value', name: 'mAP', min: 0, max: 1 },
        series: [
          { name: 'mAP50', type: 'line', smooth: true, data: data.map(d => d.metrics_mAP50_B) },
          { name: 'mAP50-95', type: 'line', smooth: true, data: data.map(d => d.metrics_mAP50_95_B) }
        ]
      }, true)
    },
    // Precision/Recall
    initPRChart(data) {
      const dom = this.$refs.prChart
      if (!dom) return
      this.prChart = echarts.init(dom, 'macarons')
      const epochs = data.map(d => 'E' + d.epoch)
      this.prChart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['Precision', 'Recall'], top: 0 },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: epochs, axisLabel: { rotate: 45, fontSize: 10 } },
        yAxis: { type: 'value', name: 'Value', min: 0, max: 1 },
        series: [
          { name: 'Precision', type: 'line', smooth: true, data: data.map(d => d.metrics_precision_B) },
          { name: 'Recall', type: 'line', smooth: true, data: data.map(d => d.metrics_recall_B) }
        ]
      }, true)
    },
    // Learning Rate
    initLRChart(data) {
      const dom = this.$refs.lrChart
      if (!dom) return
      this.lrChart = echarts.init(dom, 'macarons')
      const epochs = data.map(d => 'E' + d.epoch)
      this.lrChart.setOption({
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
      }, true)
    }
  }
}
</script>

<style scoped>
.training-detail-container {
  padding-bottom: 20px;
}
.info-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.info-value {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
.chart-container {
  width: 100%;
  height: 350px;
}
</style>
