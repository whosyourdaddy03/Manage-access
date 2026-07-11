<template>
  <div class="app-container">
    <!-- ===== 已注册模型列表 ===== -->
    <el-card style="margin-bottom: 20px;">
      <div slot="header" class="card-header">
        <span><i class="el-icon-collection-tag"></i> 已注册模型列表</span>
        <div style="float: right;">
          <el-button size="mini" icon="el-icon-folder-opened" @click="scanLocalDir" :loading="scanning">
            扫描本地
          </el-button>
          <el-button size="mini" type="primary" icon="el-icon-plus" @click="showRegisterDialog">
            注册模型
          </el-button>
        </div>
      </div>

      <el-table :data="modelList" v-loading="loading" stripe style="width: 100%">
        <el-table-column label="序号" type="index" width="55" align="center" />
        <el-table-column label="模型名称" prop="modelName" min-width="180" />
        <el-table-column label="版本" prop="modelVersion" width="70" align="center" />
        <el-table-column label="类型" prop="modelType" width="100" align="center" />
        <el-table-column label="mAP50" prop="metricsMap" width="90" align="center">
          <template slot-scope="s">{{ s.row.metricsMap != null ? s.row.metricsMap.toFixed(4) : '--' }}</template>
        </el-table-column>
        <el-table-column label="推理速度(ms)" prop="metricsSpeed" width="120" align="center">
          <template slot-scope="s">{{ s.row.metricsSpeed != null ? s.row.metricsSpeed.toFixed(2) : '--' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template slot-scope="s">
            <el-tag :type="s.row.status === 'in_use' ? 'success' : 'info'" size="small">
              {{ s.row.status === 'in_use' ? '使用中' : '归档' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="关联任务" prop="trainingTaskId" width="100" align="center" />
        <el-table-column label="操作" width="240" align="center" fixed="right">
          <template slot-scope="s">
            <el-button size="mini" type="success" plain
              :disabled="s.row.status === 'in_use'"
              @click="handleSetInUse(s.row)">启用</el-button>
            <el-button size="mini" type="primary" plain @click="showEditDialog(s.row)">编辑</el-button>
            <el-button size="mini" type="danger" plain @click="handleDelete(s.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && modelList.length === 0" description="暂无已注册模型" />
    </el-card>

    <!-- ===== 模型版本对比 ===== -->
    <el-card>
      <div slot="header" class="card-header">
        <span><i class="el-icon-s-marketing"></i> 模型版本对比</span>
        <div style="float: right; display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 13px; color: #909399;">选择对比模型:</span>
          <el-select v-model="compareIds" multiple placeholder="选择模型" size="small" style="width: 260px;"
            @change="updateCompareChart">
            <el-option v-for="m in modelList" :key="m.id"
              :label="m.modelName" :value="m.id" />
          </el-select>
        </div>
      </div>

      <div v-if="compareModels.length >= 2" ref="compareChart" class="compare-chart"></div>
      <el-empty v-else description="请选择至少 2 个模型进行对比（在右上角下拉框中选择）" />
    </el-card>

    <!-- ===== 注册/编辑 对话框 ===== -->
    <el-dialog :title="dialogTitle" :visible.sync="dialogVisible" width="600px" :close-on-click-modal="false">
      <el-form ref="modelForm" :model="form" :rules="formRules" label-width="120px" size="small">
        <el-form-item label="模型名称" prop="modelName">
          <el-input v-model="form.modelName" placeholder="如: Det-Fly 基准模型 V1.0" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="版本" prop="modelVersion">
              <el-input v-model="form.modelVersion" placeholder="1.0" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模型类型" prop="modelType">
              <el-select v-model="form.modelType" placeholder="选择" style="width:100%;">
                <el-option label="YOLOv8s" value="YOLOv8s" />
                <el-option label="YOLOv8n" value="YOLOv8n" />
                <el-option label="YOLOv8m" value="YOLOv8m" />
                <el-option label="YOLOv8l" value="YOLOv8l" />
                <el-option label="YOLOv8x" value="YOLOv8x" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="文件路径" prop="sourcePath">
          <el-input v-model="form.sourcePath" placeholder="如: D:\BaiduNetdiskDownload\train2\weights\best.pt" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="mAP50" prop="metricsMap">
              <el-input-number v-model="form.metricsMap" :min="0" :max="1" :step="0.01" :precision="4" style="width:100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="推理速度(ms)" prop="metricsSpeed">
              <el-input-number v-model="form.metricsSpeed" :min="0" :step="0.1" :precision="2" style="width:100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="关联训练任务">
          <el-input v-model="form.trainingTaskId" placeholder="如: train9 (可选)" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="备注信息(可选)" />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="dialogVisible = false">取消</el-button>
        <el-button size="small" type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </div>
    </el-dialog>

    <!-- ===== 扫描结果对话框 ===== -->
    <el-dialog title="扫描本地模型文件" :visible.sync="scanDialogVisible" width="500px">
      <el-form label-width="100px" size="small">
        <el-form-item label="扫描目录">
          <el-input v-model="scanDirPath" placeholder="如: D:\BaiduNetdiskDownload\train2\weights" />
        </el-form-item>
      </el-form>
      <el-table v-if="scanResult.length > 0" :data="scanResult" stripe size="small" style="width:100%;">
        <el-table-column label="文件名" prop="file_name" />
        <el-table-column label="操作" width="100" align="center">
          <template slot-scope="s">
            <el-button size="mini" type="primary" @click="quickRegister(s.row)">注册</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="scanDone && scanResult.length === 0" description="未发现未注册的新模型文件" />
      <div slot="footer">
        <el-button size="small" @click="scanDialogVisible = false">关闭</el-button>
        <el-button size="small" type="primary" :loading="scanning" @click="doScan">开始扫描</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import * as echarts from 'echarts'
import { listModels, registerModel, updateModel, deleteModel, setModelInUse, scanLocalModels } from '@/api/visualization/model'

export default {
  name: 'ModelCenter',
  data() {
    return {
      loading: false,
      modelList: [],
      // 对比
      compareIds: [],
      compareChart: null,
      // 注册/编辑 对话框
      dialogVisible: false,
      dialogTitle: '注册模型',
      isEdit: false,
      submitting: false,
      form: this.initForm(),
      formRules: {
        modelName: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
        sourcePath: [{ required: true, message: '请输入文件路径', trigger: 'blur' }]
      },
      // 扫描
      scanning: false,
      scanDialogVisible: false,
      scanDirPath: 'D:\\BaiduNetdiskDownload\\train2\\weights',
      scanResult: [],
      scanDone: false
    }
  },
  computed: {
    compareModels() {
      return this.modelList.filter(m => this.compareIds.includes(m.id))
    }
  },
  mounted() {
    this.fetchData()
  },
  beforeDestroy() {
    if (this.compareChart) { this.compareChart.dispose(); this.compareChart = null }
  },
  methods: {
    initForm() {
      return {
        id: null,
        modelName: '',
        modelVersion: '1.0',
        modelType: 'YOLOv8s',
        sourcePath: '',
        trainingTaskId: '',
        metricsMap: null,
        metricsSpeed: null,
        status: 'archived',
        remark: ''
      }
    },
    // ===== 数据加载 =====
    fetchData() {
      this.loading = true
      listModels().then(res => {
        this.modelList = res.data || []
        this.$nextTick(() => this.updateCompareChart())
      }).catch(() => {
        this.$modal.msgError('获取模型列表失败')
      }).finally(() => { this.loading = false })
    },
    // ===== 注册/编辑 =====
    showRegisterDialog() {
      this.isEdit = false
      this.dialogTitle = '注册模型'
      this.form = this.initForm()
      this.dialogVisible = true
      this.$nextTick(() => { if (this.$refs.modelForm) this.$refs.modelForm.clearValidate() })
    },
    showEditDialog(row) {
      this.isEdit = true
      this.dialogTitle = '编辑模型'
      this.form = { ...row }
      this.dialogVisible = true
      this.$nextTick(() => { if (this.$refs.modelForm) this.$refs.modelForm.clearValidate() })
    },
    submitForm() {
      this.$refs.modelForm.validate(valid => {
        if (!valid) return
        this.submitting = true
        const action = this.isEdit ? updateModel(this.form) : registerModel(this.form)
        action.then(() => {
          this.$modal.msgSuccess(this.isEdit ? '更新成功' : '注册成功')
          this.dialogVisible = false
          this.fetchData()
        }).catch(() => {
          this.$modal.msgError(this.isEdit ? '更新失败' : '注册失败')
        }).finally(() => { this.submitting = false })
      })
    },
    handleDelete(row) {
      this.$confirm(`确定删除模型「${row.modelName}」?`, '确认', { type: 'warning' }).then(() => {
        deleteModel(row.id).then(() => {
          this.$modal.msgSuccess('删除成功')
          this.compareIds = this.compareIds.filter(id => id !== row.id)
          this.fetchData()
        }).catch(() => this.$modal.msgError('删除失败'))
      }).catch(() => {})
    },
    handleSetInUse(row) {
      setModelInUse(row.id).then(() => {
        this.$modal.msgSuccess('已切换为使用中')
        this.fetchData()
      }).catch(() => this.$modal.msgError('操作失败'))
    },
    // ===== 扫描本地 =====
    scanLocalDir() {
      this.scanResult = []
      this.scanDone = false
      this.scanDialogVisible = true
    },
    doScan() {
      if (!this.scanDirPath) { this.$modal.msgError('请输入扫描目录'); return }
      this.scanning = true
      scanLocalModels(this.scanDirPath).then(res => {
        this.scanResult = res.data || []
        this.scanDone = true
        if (this.scanResult.length === 0) {
          this.$modal.msgInfo('未发现未注册的新模型文件')
        }
      }).catch(() => {
        this.$modal.msgError('扫描失败')
      }).finally(() => { this.scanning = false })
    },
    quickRegister(row) {
      this.form = this.initForm()
      this.form.sourcePath = row.full_path
      this.form.modelName = 'Det-Fly ' + row.file_name.replace('.pt', '')
      this.dialogTitle = '快速注册 - ' + row.file_name
      this.isEdit = false
      this.scanDialogVisible = false
      this.dialogVisible = true
    },
    // ===== 对比图表 =====
    updateCompareChart() {
      this.$nextTick(() => {
        const dom = this.$refs.compareChart
        if (!dom) return
        const models = this.compareModels
        if (models.length < 2) {
          if (this.compareChart) { this.compareChart.dispose(); this.compareChart = null }
          return
        }

        if (!this.compareChart) {
          this.compareChart = echarts.init(dom)
        }

        const names = models.map(m => m.modelName)
        const mapData = models.map(m => m.metricsMap != null ? m.metricsMap : 0)
        const speedData = models.map(m => m.metricsSpeed != null ? m.metricsSpeed : 0)

        this.compareChart.setOption({
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          legend: { data: ['mAP50', '推理速度 (ms)'], top: 0 },
          grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
          xAxis: {
            type: 'category',
            data: names,
            axisLabel: { rotate: 15, fontSize: 11 }
          },
          yAxis: [
            { type: 'value', name: 'mAP50', min: 0, max: 1 },
            { type: 'value', name: '推理速度 (ms)', position: 'right' }
          ],
          series: [
            {
              name: 'mAP50',
              type: 'bar',
              data: mapData,
              itemStyle: { color: '#409eff' },
              barMaxWidth: 30,
              label: { show: true, position: 'top', formatter: p => p.value.toFixed(4) }
            },
            {
              name: '推理速度 (ms)',
              type: 'bar',
              yAxisIndex: 1,
              data: speedData,
              itemStyle: { color: '#67c23a' },
              barMaxWidth: 30,
              label: { show: true, position: 'top', formatter: p => p.value.toFixed(2) }
            }
          ]
        }, true)
      })
    }
  }
}
</script>

<style scoped>
.compare-chart {
  width: 100%;
  height: 420px;
}
</style>
