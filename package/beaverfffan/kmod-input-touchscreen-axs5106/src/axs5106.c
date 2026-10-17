// SPDX-License-Identifier: GPL-2.0
/* AXS5106 Linux I2C Touchscreen Driver */

#include <linux/module.h>
#include <linux/init.h>
#include <linux/i2c.h>
#include <linux/input.h>
#include <linux/input/mt.h>
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/of.h>

#define DRIVER_NAME "axs5106_ts"

struct axs5106_data {
	struct i2c_client *client;
	struct input_dev *input;
	struct gpio_desc *reset_gpio;
	struct gpio_desc *irq_gpio;
};

static irqreturn_t axs5106_irq_handler(int irq, void *dev_id)
{
	struct axs5106_data *data = dev_id;
	u8 buf[6] = {0};
	u8 reg = 0x01;

	i2c_master_send(data->client, &reg, 1);
	if (i2c_master_recv(data->client, buf, sizeof(buf)) != sizeof(buf)) {
		dev_err(&data->client->dev, "Failed to read touch data\n");
		return IRQ_HANDLED;
	}

	u16 x = (buf[3] | ((buf[2] & 0x0F) << 8));
	u16 y = (buf[5] | ((buf[4] & 0x0F) << 8));
	bool pressed = ((buf[2] & 0xF0) != 0x40);

	input_report_key(data->input, BTN_TOUCH, pressed);
	input_report_abs(data->input, ABS_MT_POSITION_X, x);
	input_report_abs(data->input, ABS_MT_POSITION_Y, y);
	input_mt_sync(data->input);
	input_sync(data->input);

	return IRQ_HANDLED;
}

static int axs5106_probe(struct i2c_client *client)
{
	struct axs5106_data *data;
	struct input_dev *input;
	int err;

	dev_info(&client->dev, "AXS5106 probe start\n");

	data = devm_kzalloc(&client->dev, sizeof(*data), GFP_KERNEL);
	if (!data)
		return -ENOMEM;

	data->client = client;

	// 获取 reset GPIO
	data->reset_gpio = devm_gpiod_get_optional(&client->dev, "reset", GPIOD_OUT_LOW);
	if (IS_ERR(data->reset_gpio)) {
		dev_err(&client->dev, "Failed to get reset GPIO\n");
		return PTR_ERR(data->reset_gpio);
	}

	if (data->reset_gpio) {
		dev_info(&client->dev, "Performing hardware reset\n");
		gpiod_set_value_cansleep(data->reset_gpio, 0);
		msleep(20);
		gpiod_set_value_cansleep(data->reset_gpio, 1);
		msleep(100);
	}

	// 获取 IRQ GPIO
	data->irq_gpio = devm_gpiod_get_optional(&client->dev, "irq", GPIOD_IN);
	if (IS_ERR(data->irq_gpio)) {
		dev_info(&client->dev, "irq = %d\n", gpiod_to_irq(data->irq_gpio));
		dev_err(&client->dev, "Failed to get IRQ GPIO\n");
		return PTR_ERR(data->irq_gpio);
	}

	input = devm_input_allocate_device(&client->dev);
	if (!input)
		return -ENOMEM;

	input->name = "AXS5106 Touchscreen";
	input->id.bustype = BUS_I2C;
	input->dev.parent = &client->dev;

	input_set_abs_params(input, ABS_MT_POSITION_X, 0, 320, 0, 0);
	input_set_abs_params(input, ABS_MT_POSITION_Y, 0, 172, 0, 0);
	input_set_capability(input, EV_KEY, BTN_TOUCH);
	input_mt_init_slots(input, 1, INPUT_MT_DIRECT);

	data->input = input;

	i2c_set_clientdata(client, data);

	err = devm_request_threaded_irq(&client->dev,
		gpiod_to_irq(data->irq_gpio),
		NULL, axs5106_irq_handler,
		IRQF_TRIGGER_FALLING | IRQF_ONESHOT,
		client->name, data);
	if (err) {
		dev_err(&client->dev, "Failed to request IRQ\n");
		return err;
	}

	err = input_register_device(input);
	if (err)
		return err;

	dev_info(&client->dev, "AXS5106 touchscreen initialized\n");
	return 0;
}

static const struct of_device_id axs5106_of_match[] = {
	{ .compatible = "chipone,axs5106" },
	{ }
};
MODULE_DEVICE_TABLE(of, axs5106_of_match);

static const struct i2c_device_id axs5106_id[] = {
	{ DRIVER_NAME, 0 },
	{ }
};
MODULE_DEVICE_TABLE(i2c, axs5106_id);

static struct i2c_driver axs5106_driver = {
	.driver = {
		.name = DRIVER_NAME,
		.of_match_table = axs5106_of_match,
	},
	.probe = axs5106_probe,
	.id_table = axs5106_id,
};

module_i2c_driver(axs5106_driver);

MODULE_AUTHOR("Fish");
MODULE_DESCRIPTION("AXS5106 I2C Touchscreen Driver");
MODULE_LICENSE("GPL");
