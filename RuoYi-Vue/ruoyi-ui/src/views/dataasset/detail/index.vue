<template>
  <div class="app-container">
    <el-card>
      <div slot="header" class="card-header">
        <span><i class="el-icon-view"></i> 标注可视化 - {{ imageId }}</span>
        <div style="float: right;">
          <el-button size="mini" icon="el-icon-arrow-left" @click="goBack">返回</el-button>
          <el-button size="mini" icon="el-icon-refresh" @click="loadData">重新加载</el-button>
        </div>
      </div>

      <el-row :gutter="20">
        <!-- 左侧: 标注图片 -->
        <el-col :xs="24" :lg="16">
          <el-card shadow="never">
            <div slot="header">
              <span>图片标注预览</span>
              <div style="float: right; font-size: 12px; color: #909399;">
                滚轮缩放 | 拖拽平移
                <el-button size="mini" type="text" @click="zoomIn" style="margin-left: 10px;">放大</el-button>
                <el-button size="mini" type="text" @click="zoomOut">缩小</el-button>
                <el-button size="mini" type="text" @click="resetZoom">重置</el-button>
              </div>
            </div>
            <div class="canvas-wrapper" ref="canvasWrapper">
              <canvas
                ref="annotationCanvas"
                class="annotation-canvas"
                @wheel.prevent="handleWheel"
                @mousedown="handleMouseDown"
                @mousemove="handleMouseMove"
                @mouseup="handleMouseUp"
                @mouseleave="handleMouseUp"
              ></canvas>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧: 标注信息 -->
        <el-col :xs="24" :lg="8">
          <el-card shadow="never">
            <div slot="header"><span>标注信息</span></div>
            <div v-loading="loading" style="min-height: 200px;">
              <el-descriptions v-if="annotationInfo" column="1" border size="small">
                <el-descriptions-item label="图片ID">{{ annotationInfo.id }}</el-descriptions-item>
                <el-descriptions-item label="图片宽度">{{ annotationInfo.width }} px</el-descriptions-item>
                <el-descriptions-item label="图片高度">{{ annotationInfo.height }} px</el-descriptions-item>
                <el-descriptions-item label="标注框 - Xmin">{{ annotationInfo.xmin }}</el-descriptions-item>
                <el-descriptions-item label="标注框 - Ymin">{{ annotationInfo.ymin }}</el-descriptions-item>
                <el-descriptions-item label="标注框 - Xmax">{{ annotationInfo.xmax }}</el-descriptions-item>
                <el-descriptions-item label="标注框 - Ymax">{{ annotationInfo.ymax }}</el-descriptions-item>
                <el-descriptions-item label="框宽度">{{ annotationInfo.xmax - annotationInfo.xmin }} px</el-descriptions-item>
                <el-descriptions-item label="框高度">{{ annotationInfo.ymax - annotationInfo.ymin }} px</el-descriptions-item>
                <el-descriptions-item label="深度(depth)">{{ annotationInfo.depth }}</el-descriptions-item>
                <el-descriptions-item label="姿态(pose)">{{ annotationInfo.pose }}</el-descriptions-item>
                <el-descriptions-item label="是否分割(segmented)">{{ annotationInfo.segmented }}</el-descriptions-item>
              </el-descriptions>
              <el-empty v-else-if="!loading" description="无标注数据" />
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script>
import { queryPicture, queryRawData, getRawImageUrl } from '@/api/visualization/dataset'

export default {
  name: 'ImageDetail',
  data() {
    return {
      imageId: '',
      loading: false,
      annotationInfo: null,
      // Canvas 相关
      imageObj: null,
      scale: 1,
      offsetX: 0,
      offsetY: 0,
      isDragging: false,
      dragStartX: 0,
      dragStartY: 0,
      redBox: null
    }
  },
  created() {
    this.imageId = this.$route.params.id || ''
  },
  mounted() {
    if (this.imageId) {
      this.loadData()
    }
  },
  beforeDestroy() {
    if (this.imageObj) {
      this.imageObj.onload = null
    }
  },
  methods: {
    loadData() {
      if (!this.imageId) return
      this.loading = true

      // 并行获取标注数据和图片
      Promise.all([
        queryRawData(this.imageId),
        this.loadImage()
      ]).then(([rawResponse]) => {
        const rawData = rawResponse.data
        if (rawData) {
          this.annotationInfo = rawData
          // 解析标注框信息
          this.redBox = {
            xmin: parseInt(rawData.xmin),
            ymin: parseInt(rawData.ymin),
            xmax: parseInt(rawData.xmax),
            ymax: parseInt(rawData.ymax)
          }
          this.$nextTick(() => {
            this.drawCanvas()
          })
        } else {
          this.$modal.msgError('未找到标注数据')
        }
      }).catch(err => {
        this.$modal.msgError('加载数据失败：' + (err.message || '未知错误'))
      }).finally(() => {
        this.loading = false
      })
    },
    loadImage() {
      return new Promise((resolve, reject) => {
        const img = new Image()
        img.crossOrigin = 'anonymous'
        img.onload = () => {
          this.imageObj = img
          resolve()
        }
        img.onerror = () => {
          reject(new Error('图片加载失败'))
        }
        img.src = getRawImageUrl(this.imageId)
      })
    },
    drawCanvas() {
      const canvas = this.$refs.annotationCanvas
      const wrapper = this.$refs.canvasWrapper
      if (!canvas || !wrapper || !this.imageObj) return

      // 设置canvas尺寸适应wrapper
      const containerWidth = wrapper.clientWidth
      const containerHeight = Math.max(500, containerWidth * 0.6)
      canvas.width = containerWidth
      canvas.height = containerHeight
      wrapper.style.height = containerHeight + 'px'

      const ctx = canvas.getContext('2d')
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // 计算初始缩放使图片适应画布
      const imgW = this.imageObj.width
      const imgH = this.imageObj.height
      const scaleX = (canvas.width - 40) / imgW
      const scaleY = (canvas.height - 40) / imgH
      this.scale = Math.min(scaleX, scaleY, 1) // 不放大超过原始尺寸

      // 居中显示
      const displayW = imgW * this.scale
      const displayH = imgH * this.scale
      this.offsetX = (canvas.width - displayW) / 2
      this.offsetY = (canvas.height - displayH) / 2

      this.renderCanvas(ctx)
    },
    renderCanvas(ctx) {
      const canvas = ctx.canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // 绘制背景
      ctx.fillStyle = '#f0f2f5'
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      // 绘制图片
      const imgW = this.imageObj.width
      const imgH = this.imageObj.height
      const displayW = imgW * this.scale
      const displayH = imgH * this.scale
      ctx.drawImage(this.imageObj, this.offsetX, this.offsetY, displayW, displayH)

      // 绘制红色标注框
      if (this.redBox) {
        const scale = this.scale
        const x = this.offsetX + this.redBox.xmin * scale
        const y = this.offsetY + this.redBox.ymin * scale
        const w = (this.redBox.xmax - this.redBox.xmin) * scale
        const h = (this.redBox.ymax - this.redBox.ymin) * scale

        ctx.strokeStyle = '#ff0000'
        ctx.lineWidth = 3
        ctx.strokeRect(x, y, w, h)

        // 添加半透明填充
        ctx.fillStyle = 'rgba(255, 0, 0, 0.1)'
        ctx.fillRect(x, y, w, h)

        // 绘制标注标签
        ctx.fillStyle = 'rgba(255, 0, 0, 0.8)'
        ctx.fillRect(x, y - 24, 80, 20)
        ctx.fillStyle = '#ffffff'
        ctx.font = '12px Arial'
        ctx.fillText('Ground-Truth', x + 4, y - 9)

      }
    },
    // 缩放
    zoomIn() {
      this.scale = Math.min(this.scale * 1.2, 3)
      this.redraw()
    },
    zoomOut() {
      this.scale = Math.max(this.scale / 1.2, 0.1)
      this.redraw()
    },
    resetZoom() {
      this.drawCanvas()
    },
    handleWheel(e) {
      const delta = e.deltaY > 0 ? 0.9 : 1.1
      this.scale = Math.max(0.1, Math.min(this.scale * delta, 3))
      this.redraw()
    },
    // 拖拽
    handleMouseDown(e) {
      const rect = this.$refs.annotationCanvas.getBoundingClientRect()
      this.isDragging = true
      this.dragStartX = e.clientX - this.offsetX
      this.dragStartY = e.clientY - this.offsetY
    },
    handleMouseMove(e) {
      if (!this.isDragging) return
      this.offsetX = e.clientX - this.dragStartX
      this.offsetY = e.clientY - this.dragStartY
      this.redraw()
    },
    handleMouseUp() {
      this.isDragging = false
    },
    redraw() {
      const canvas = this.$refs.annotationCanvas
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      this.renderCanvas(ctx)
    },
    goBack() {
      this.$router.back()
    }
  }
}
</script>

<style scoped>
.canvas-wrapper {
  position: relative;
  overflow: hidden;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #f0f2f5;
}
.annotation-canvas {
  width: 100%;
  height: 100%;
  cursor: grab;
  display: block;
}
.annotation-canvas:active {
  cursor: grabbing;
}
</style>
