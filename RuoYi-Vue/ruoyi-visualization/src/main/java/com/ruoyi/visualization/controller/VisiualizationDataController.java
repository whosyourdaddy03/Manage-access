package com.ruoyi.visualization.controller;

import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.common.annotation.Anonymous;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.visualization.service.VisiualizationDataService;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.util.CollectionUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;

@RestController
@RequestMapping("/visiualization/data")
public class VisiualizationDataController {
    private final Logger logger = LoggerFactory.getLogger(VisiualizationDataController.class);

    @Autowired
    private VisiualizationDataService visiualizationDataService;

    /**
     * 获取xml原始数据
     *
     * @param id 标签id
     * @return 样例报文
     * {
     * "msg": "响应成功",
     * "code": 200,
     * "data": {
     * "ymin": "760",
     * "xmin": "1146",
     * "depth": "3",
     * "ymax": "808",
     * "xmax": "1333",
     * "pose": "Unspecified",
     * "width": "3840",
     * "id": "0100001",
     * "segmented": "0",
     * "height": "2160"
     * }
     * }
     */
    @GetMapping("/queryRawData")
    @Anonymous

    public AjaxResult queryRawData(@RequestParam("id") String id) {
        logger.info("获取xml原始数据开始，id：{}", id);
        JSONObject jsonObject = visiualizationDataService.queryRawData(id);
        if (CollectionUtils.isEmpty(jsonObject)) {
            return AjaxResult.error("请求id有误，无数据返回");
        }
        logger.info("获取xml原始数据结束，数据信息：{}",jsonObject);
        return AjaxResult.success(jsonObject);
    }


    /**
     * 绘制图片
     * @param id 标签id
     * @param response 服务器响应对象
     */
    @GetMapping("/queryPicture")
    @Anonymous
    public void queryPicture(@RequestParam("id") String id, HttpServletResponse response) {
        logger.info("绘制图片开始，id:{}",id);
        try {
            visiualizationDataService.queryPicture(id,response);
        } catch (IOException e) {
            logger.error("绘制图片异常",e);
        }
        logger.info("获取xml原始数据结束");
    }

    /**
     * 模型预测结果查询
     * @return
     */
    @GetMapping("/queryPrediction")
    @Anonymous
    public AjaxResult queryPrediction(){
        logger.info("模型预测结果查询开始");
        JSONArray jsonArray = visiualizationDataService.queryPrediction();
        if (CollectionUtils.isEmpty(jsonArray)) {
            return AjaxResult.error("数据异常，请稍后再试");
        }
        logger.info("模型预测结果查询结束，模型预测结果：{}",jsonArray);
        return AjaxResult.success(jsonArray);
    }

    /**
     * 实时模型生成
     * @return
     */
    @GetMapping("/generationModel")
    @Anonymous
    public AjaxResult generationModel(){
        logger.info("实时模型生成开始");
        visiualizationDataService.generationModel();

        logger.info("实时模型生成结束");
        return AjaxResult.success();
    }

    /**
     * 查询所有不同的epoch id组
     * @return id列表
     */
    @GetMapping("/queryAllEpochIds")
    @Anonymous
    public AjaxResult queryAllEpochIds() {
        logger.info("查询所有epoch id组开始");
        JSONArray jsonArray = visiualizationDataService.queryAllEpochIds();
        logger.info("查询所有epoch id组结束");
        return AjaxResult.success(jsonArray);
    }

    /**
     * 查询所有epoch结果
     * @return epoch结果列表
     */
    @GetMapping("/queryEpochResults")
    @Anonymous
    public AjaxResult queryEpochResults() {
        logger.info("查询所有epoch结果开始");
        JSONArray jsonArray = visiualizationDataService.queryEpochResults();
        logger.info("查询所有epoch结果结束");
        return AjaxResult.success(jsonArray);
    }

    /**
     * 按指定id分组查询epoch结果
     * @param id 分组id
     * @return epoch结果列表
     */
    @GetMapping("/queryEpochResultsByGroup")
    @Anonymous
    public AjaxResult queryEpochResultsByGroup(@RequestParam("id") String id) {
        logger.info("按id查询epoch结果开始，id：{}", id);
        JSONArray jsonArray = visiualizationDataService.queryEpochResultsByGroup(id);
        logger.info("按id查询epoch结果结束");
        return AjaxResult.success(jsonArray);
    }

    /**
     * 查询数据集列表
     * @return 数据集列表
     */
    @GetMapping("/queryDatasetList")
    @Anonymous
    public AjaxResult queryDatasetList() {
        logger.info("查询数据集列表开始");
        JSONArray jsonArray = visiualizationDataService.queryDatasetList();
        logger.info("查询数据集列表结束");
        return AjaxResult.success(jsonArray);
    }

    /**
     * 分页查询图片列表(扫描本地目录)
     * @param folder 文件夹名
     * @param pageNum 页码
     * @param pageSize 每页条数
     * @return 图片列表
     */
    @GetMapping("/queryImageList")
    @Anonymous
    public AjaxResult queryImageList(@RequestParam("folder") String folder,
                                      @RequestParam(value = "pageNum", defaultValue = "1") int pageNum,
                                      @RequestParam(value = "pageSize", defaultValue = "20") int pageSize) {
        logger.info("查询图片列表开始，folder：{}，pageNum：{}，pageSize：{}", folder, pageNum, pageSize);
        JSONObject result = visiualizationDataService.queryImageList(folder, pageNum, pageSize);
        logger.info("查询图片列表结束，总数：{}", result.get("total"));
        return AjaxResult.success(result);
    }

    /**
     * 获取原始图片(不绘制标注)
     * @param id 图片id
     * @param response 服务器响应对象
     */
    @GetMapping("/getRawImage")
    @Anonymous
    public void getRawImage(@RequestParam("id") String id, HttpServletResponse response) {
        logger.info("获取原始图片开始，id：{}", id);
        try {
            visiualizationDataService.getRawImage(id, response);
        } catch (IOException e) {
            logger.error("获取原始图片异常", e);
        }
        logger.info("获取原始图片结束");
    }
}
