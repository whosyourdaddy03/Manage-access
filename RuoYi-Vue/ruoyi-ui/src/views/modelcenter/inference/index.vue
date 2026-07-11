<template>
  <div class="app-container">
    <!-- ===== 单张图片检测 ===== -->
    <el-card style="margin-bottom: 20px;">
      <div slot="header" class="card-header">
        <span><i class="el-icon-picture"></i> 单张图片检测</span>
      </div>
      <el-row :gutter="20">
        <el-col :span="10">
          <el-upload
            ref="singleUpload"
            drag
            accept="image/jpeg,image/png,image/jpg"
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleSingleSelect"
            style="text-align:center;">
            <i class="el-icon-upload" style="font-size: 48px; color: #409eff;"></i>
            <div class="el-upload__text">拖拽图片到此处 或 <em>点击选择</em></div>
            <div slot="tip" class="el-upload__tip" style="padding: 0 10px;">
              支持 jpg/png 格式，建议尺寸不超过 3840×2160
            </div>
          </el-upload>
          <div v-if="singleFileName" style="margin-top: 10px; text-align: center;">
            <el-tag>{{ singleFileName }}</el-tag>
            <el-button type="primary" size="small" style="margin-left: 10px;"
              :loading="singleLoading" @click="submitSingle">开始检测</el-button>
          </div>
        </el-col>
        <el-col :span="14">
          <div v-loading="singleLoading" class="result-area">
            <template v-if="singleResultImage">
              <h4 style="margin-top: 0; color: #409eff;">
                检测结果 — 共检测到 <strong>{{ singleDetections.length }}</strong> 个目标
              </h4>
              <div class="result-image-wrapper">
                <img :src="singleResultImage" class="result-image" alt="检测结果" />
              </div>
              <el-table v-if="singleDetections.length > 0" :data="singleDetections"
                size="small" stripe style="width:100%; margin-top: 10px;" max-height="180">
                <el-table-column label="#" type="index" width="45" />
                <el-table-column label="类别" prop="class_name" width="120" />
                <el-table-column label="置信度" width="120">
                  <template slot-scope="s">{{ (s.row.confidence * 100).toFixed(1) }}%</template>
                </el-table-column>
                <el-table-column label="边界框 (xyxy)" min-width="200">
                  <template slot-scope="s">{{ s.row.bbox.join(', ') }}</template>
                </el-table-column>
              </el-table>
            </template>
            <el-empty v-else-if="!singleLoading" description="上传图片后点击「开始检测」查看结果" />
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- ===== 批量图片检测 ===== -->
    <el-card>
      <div slot="header" class="card-header">
        <span><i class="el-icon-files"></i> 批量图片检测</span>
      </div>
      <el-row :gutter="20">
        <el-col :span="10">
          <el-upload
            ref="batchUpload"
            drag
            accept=".zip"
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleBatchSelect"
            style="text-align:center;">
            <i class="el-icon-upload2" style="font-size: 48px; color: #67c23a;"></i>
            <div class="el-upload__text">拖拽 zip 包到此处 或 <em>点击选择</em></div>
            <div slot="tip" class="el-upload__tip" style="padding: 0 10px;">
              打包图片为 zip 上传，系统自动解压并逐张推理
            </div>
          </el-upload>
          <div v-if="batchFileName" style="margin-top: 10px; text-align: center;">
            <el-tag>{{ batchFileName }}</el-tag>
            <el-button type="success" size="small" style="margin-left: 10px;"
              :loading="batchLoading" @click="submitBatch">开始批量检测</el-button>
          </div>
        </el-col>
        <el-col :span="14">
          <h4 style="margin-top: 0; color: #67c23a;">批量任务列表</h4>
          <el-table :data="batchTasks" v-loading="batchListLoading" stripe size="small" style="width:100%;">
            <el-table-column label="任务ID" prop="taskId" width="100" />
            <el-table-column label="状态" width="100" align="center">
              <template slot-scope="s">
                <el-tag :type="s.row.status === 'COMPLETED' ? 'success' : s.row.status === 'FAILED' ? 'danger' : 'warning'" size="small">
                  {{ s.row.status === 'PROCESSING' ? '处理中' : s.row.status === 'COMPLETED' ? '已完成' : '失败' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="进度" width="140">
              <template slot-scope="s">
                <el-progress v-if="s.row.status === 'PROCESSING'" :percentage="Math.round(s.row.percent)" :stroke-width="14" />
                <span v-else>{{ s.row.completed }}/{{ s.row.total }}</span>
              </template>
            </el-table-column>
            <el-table-column label="当前文件" prop="currentFile" min-width="150" />
            <el-table-column label="操作" width="100" align="center">
              <template slot-scope="s">
                <el-button v-if="s.row.status === 'COMPLETED'" type="primary" size="mini" icon="el-icon-download"
                  @click="downloadBatch(s.row)">下载</el-button>
                <el-button v-else-if="s.row.status === 'PROCESSING'" type="info" size="mini"
                  @click="refreshBatchTasks">刷新</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="batchTasks.length === 0" description="暂无批量检测任务" />
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script>
import {
  singleInference,
  startBatchInference,
  getBatchStatus,
  listBatchTasks,
  getBatchDownloadUrl
} from '@/api/visualization/inference'

export default {
  name: 'OnlineInference',
  data() {
    return {
      // 单张
      singleFileName: '',
      singleFile: null,
      singleLoading: false,
      singleResultImage: null,
      singleDetections: [],
      // 批量
      batchFileName: '',
      batchFile: null,
      batchLoading: false,
      batchTasks: [],
      batchListLoading: false,
      pollTimer: null
    }
  },
  mounted() {
    this.loadBatchTasks()
  },
  beforeDestroy() {
    if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null }
  },
  methods: {
    // ===== 单张检测 =====
    handleSingleSelect(file) {
      this.singleFileName = file.name
      this.singleFile = file.raw
      this.singleResultImage = null
      this.singleDetections = []
    },
    submitSingle() {
      if (!this.singleFile) { this.$modal.msgError('请先选择图片'); return }
      this.singleLoading = true
      const formData = new FormData()
      formData.append('file', this.singleFile)

      singleInference(formData).then(res => {
        const data = res.data
        if (data.imageBase64) {
          this.singleResultImage = 'data:image/jpeg;base64,' + data.imageBase64
        }
        this.singleDetections = data.detections || []
      }).catch(err => {
        this.$modal.msgError('推理失败: ' + (err.msg || '未知错误'))
      }).finally(() => {
        this.singleLoading = false
      })
    },
    // ===== 批量检测 =====
    handleBatchSelect(file) {
      this.batchFileName = file.name
      this.batchFile = file.raw
    },
    submitBatch() {
      if (!this.batchFile) { this.$modal.msgError('请先选择 zip 包'); return }
      this.batchLoading = true
      const formData = new FormData()
      formData.append('file', this.batchFile)

      startBatchInference(formData).then(res => {
        this.$modal.msgSuccess('批量推理已启动')
        this.batchFileName = ''
        this.batchFile = null
        if (this.$refs.batchUpload) this.$refs.batchUpload.clearFiles()
        this.loadBatchTasks()
        // 启动轮询
        this.startPolling()
      }).catch(() => {
        this.$modal.msgError('启动批量推理失败')
      }).finally(() => {
        this.batchLoading = false
      })
    },
    loadBatchTasks() {
      listBatchTasks().then(res => {
        this.batchTasks = res.data || []
      }).catch(() => {})
    },
    refreshBatchTasks() {
      this.loadBatchTasks()
    },
    startPolling() {
      if (this.pollTimer) clearInterval(this.pollTimer)
      this.pollTimer = setInterval(() => {
        this.loadBatchTasks()
        // 检查是否所有任务都已完成
        const hasProcessing = this.batchTasks.some(t => t.status === 'PROCESSING')
        if (!hasProcessing) {
          clearInterval(this.pollTimer)
          this.pollTimer = null
        }
      }, 2000)
    },
    downloadBatch(task) {
      const url = getBatchDownloadUrl(task.taskId)
      const a = document.createElement('a')
      a.href = url
      a.download = 'inference_result.zip'
      a.style.display = 'none'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    }
  }
}
</script>

<style scoped>
.result-area {
  min-height: 200px;
  border: 1px dashed #dcdfe6;
  border-radius: 6px;
  padding: 15px;
}
.result-image-wrapper {
  max-height: 400px;
  overflow: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}
.result-image {
  width: 100%;
  display: block;
}
</style>
